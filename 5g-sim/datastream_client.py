# windows_etl_client.py - Windows Side
import asyncio
import websockets
import json
import socket
import threading
import time
import pandas as pd
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
import logging
from dataclasses import dataclass
from queue import Queue
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class NS3Packet:
    timestamp: float
    node_id: int
    packet_type: str
    packet_size: int
    source: Optional[str] = None
    destination: Optional[str] = None
    delay: Optional[float] = None
    throughput: Optional[float] = None

class DatabaseManager:
    def __init__(self, db_path: str = "ns3_data.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create packets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS packets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                node_id INTEGER,
                packet_type TEXT,
                packet_size INTEGER,
                source TEXT,
                destination TEXT,
                delay REAL,
                throughput REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create throughput aggregations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS throughput_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id INTEGER,
                avg_throughput REAL,
                max_throughput REAL,
                min_throughput REAL,
                packet_count INTEGER,
                window_start DATETIME,
                window_end DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON packets(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_node_id ON packets(node_id)')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized: {self.db_path}")
    
    def insert_packet(self, packet: NS3Packet):
        """Insert packet data into database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO packets (timestamp, node_id, packet_type, packet_size, 
                                   source, destination, delay, throughput)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                packet.timestamp, packet.node_id, packet.packet_type,
                packet.packet_size, packet.source, packet.destination,
                packet.delay, packet.throughput
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Database insert error: {e}")
    
    def get_recent_data(self, minutes: int = 5) -> pd.DataFrame:
        """Get recent data for dashboard"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            query = '''
                SELECT * FROM packets 
                WHERE timestamp > (strftime('%s', 'now') - ?)
                ORDER BY timestamp DESC
            '''
            
            df = pd.read_sql_query(query, conn, params=[minutes * 60])
            conn.close()
            
            return df
            
        except Exception as e:
            logger.error(f"Database query error: {e}")
            return pd.DataFrame()

class NS3ETLClient:
    def __init__(self, config: Dict):
        self.config = config
        self.db_manager = DatabaseManager()
        self.data_queue = Queue(maxsize=50000)
        self.running = False
        self.stats = {
            'packets_received': 0,
            'packets_processed': 0,
            'connection_status': 'disconnected',
            'last_activity': None
        }
    
    async def websocket_client(self):
        """WebSocket client for real-time data"""
        uri = f"ws://{self.config['vm_host']}:{self.config['websocket_port']}"
        
        while self.running:
            try:
                logger.info(f"Connecting to WebSocket: {uri}")
                async with websockets.connect(uri) as websocket:
                    self.stats['connection_status'] = 'connected'
                    logger.info("WebSocket connected successfully")
                    
                    async for message in websocket:
                        if not self.running:
                            break
                            
                        try:
                            data = json.loads(message)
                            self.process_incoming_data(data)
                            self.stats['packets_received'] += 1
                            self.stats['last_activity'] = datetime.now()
                            
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error: {e}")
                        except Exception as e:
                            logger.error(f"Message processing error: {e}")
            
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed")
                self.stats['connection_status'] = 'disconnected'
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self.stats['connection_status'] = 'error'
            
            if self.running:
                logger.info("Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
    
    def tcp_client(self):
        """TCP client as fallback"""
        while self.running:
            try:
                logger.info(f"Connecting to TCP: {self.config['vm_host']}:{self.config['tcp_port']}")
                
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.connect((self.config['vm_host'], self.config['tcp_port']))
                    logger.info("TCP connected successfully")
                    
                    buffer = ""
                    while self.running:
                        try:
                            data = sock.recv(4096).decode('utf-8')
                            if not data:
                                break
                            
                            buffer += data
                            while '\n' in buffer:
                                line, buffer = buffer.split('\n', 1)
                                if line.strip():
                                    try:
                                        json_data = json.loads(line.strip())
                                        self.process_incoming_data(json_data)
                                        self.stats['packets_received'] += 1
                                    except json.JSONDecodeError:
                                        pass
                        
                        except socket.timeout:
                            continue
                        except Exception as e:
                            logger.error(f"TCP receive error: {e}")
                            break
            
            except Exception as e:
                logger.error(f"TCP connection error: {e}")
            
            if self.running:
                logger.info("TCP reconnecting in 5 seconds...")
                time.sleep(5)
    
    def udp_listener(self):
        """UDP listener for high-throughput data"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('0.0.0.0', self.config['udp_port']))
            sock.settimeout(1.0)
            
            logger.info(f"UDP listener started on port {self.config['udp_port']}")
            
            while self.running:
                try:
                    data, addr = sock.recvfrom(65536)
                    json_data = json.loads(data.decode('utf-8'))
                    self.process_incoming_data(json_data)
                    self.stats['packets_received'] += 1
                    
                except socket.timeout:
                    continue
                except json.JSONDecodeError as e:
                    logger.error(f"UDP JSON decode error: {e}")
                except Exception as e:
                    logger.error(f"UDP error: {e}")
        
        except Exception as e:
            logger.error(f"UDP listener error: {e}")
        finally:
            sock.close()
    
    def process_incoming_data(self, data: Dict):
        """Process incoming NS-3 data"""
        try:
            # Convert to NS3Packet object
            packet = NS3Packet(
                timestamp=data.get('timestamp', time.time()),
                node_id=data.get('node_id', 0),
                packet_type=data.get('type', 'unknown'),
                packet_size=data.get('packet_size', 0),
                source=data.get('source'),
                destination=data.get('destination'),
                delay=data.get('delay'),
                throughput=data.get('throughput_mbps')
            )
            
            # Add to processing queue
            if not self.data_queue.full():
                self.data_queue.put(packet)
            else:
                logger.warning("Processing queue full - dropping data")
        
        except Exception as e:
            logger.error(f"Data processing error: {e}")
    
    def data_processor(self):
        """Process queued data for ETL pipeline"""
        batch_size = 100
        batch = []
        
        while self.running:
            try:
                # Collect batch
                while len(batch) < batch_size and not self.data_queue.empty():
                    packet = self.data_queue.get(timeout=1)
                    batch.append(packet)
                
                # Process batch
                if batch:
                    self.process_batch(batch)
                    batch.clear()
                
                time.sleep(0.1)  # Small delay to prevent CPU spinning
                
            except Exception as e:
                logger.error(f"Batch processing error: {e}")
    
    def process_batch(self, batch: List[NS3Packet]):
        """Process a batch of packets"""
        try:
            # Insert into database
            for packet in batch:
                self.db_manager.insert_packet(packet)
                self.stats['packets_processed'] += 1
            
            # Trigger real-time analytics
            self.trigger_analytics(batch)
            
            logger.debug(f"Processed batch of {len(batch)} packets")
            
        except Exception as e:
            logger.error(f"Batch processing error: {e}")
    
    def trigger_analytics(self, batch: List[NS3Packet]):
        """Trigger real-time analytics and alerts"""
        try:
            # Calculate throughput statistics
            throughput_data = [p.throughput for p in batch if p.throughput is not None]
            
            if throughput_data:
                avg_throughput = sum(throughput_data) / len(throughput_data)
                
                # Alert if throughput drops below threshold
                if avg_throughput < self.config.get('throughput_threshold', 10.0):
                    logger.warning(f"Low throughput detected: {avg_throughput:.2f} Mbps")
                    # Here you could send alerts to monitoring system
            
            # Calculate packet loss (simplified)
            tx_packets = len([p for p in batch if p.packet_type == 'packet_tx'])
            rx_packets = len([p for p in batch if p.packet_type == 'packet_rx'])
            
            if tx_packets > 0:
                packet_loss = max(0, (tx_packets - rx_packets) / tx_packets * 100)
                if packet_loss > self.config.get('packet_loss_threshold', 5.0):
                    logger.warning(f"High packet loss detected: {packet_loss:.2f}%")
        
        except Exception as e:
            logger.error(f"Analytics error: {e}")
    
    def get_dashboard_data(self) -> Dict:
        """Get data for dashboard"""
        try:
            recent_data = self.db_manager.get_recent_data(minutes=5)
            
            if recent_data.empty:
                return {"error": "No recent data"}
            
            # Calculate metrics
            throughput_data = recent_data[recent_data['throughput'].notna()]
            
            dashboard_data = {
                'stats': self.stats.copy(),
                'metrics': {
                    'total_packets': len(recent_data),
                    'avg_throughput': throughput_data['throughput'].mean() if not throughput_data.empty else 0,
                    'max_throughput': throughput_data['throughput'].max() if not throughput_data.empty else 0,
                    'active_nodes': recent_data['node_id'].nunique(),
                    'avg_packet_size': recent_data['packet_size'].mean(),
                    'total_data_mb': recent_data['packet_size'].sum() / (1024 * 1024)
                },
                'recent_data': recent_data.tail(100).to_dict('records')
            }
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Dashboard data error: {e}")
            return {"error": str(e)}
    
    def start_client(self):
        """Start all client services"""
        self.running = True
        logger.info("Starting NS3 ETL Client...")
        
        # Start data processor
        processor_thread = threading.Thread(target=self.data_processor, daemon=True)
        processor_thread.start()
        
        # Start TCP client (fallback)
        tcp_thread = threading.Thread(target=self.tcp_client, daemon=True)
        tcp_thread.start()
        
        # Start UDP listener
        udp_thread = threading.Thread(target=self.udp_listener, daemon=True)
        udp_thread.start()
        
        logger.info("ETL Client started successfully")
        logger.info(f"Listening for UDP on port {self.config['udp_port']}")
        logger.info(f"TCP fallback: {self.config['vm_host']}:{self.config['tcp_port']}")
    
    def stop_client(self):
        """Stop all services"""
        self.running = False
        logger.info("Stopping NS3 ETL Client...")


# Configuration
def get_default_config():
    return {
        'vm_host': '192.168.1.50',  # Your Ubuntu VM IP
        'websocket_port': 8765,
        'tcp_port': 8766,
        'udp_port': 9001,  # Local UDP listening port
        'throughput_threshold': 10.0,  # Mbps
        'packet_loss_threshold': 5.0,  # Percentage
        'db_path': 'ns3_realtime.db'
    }


# Main execution
async def main():
    config = get_default_config()
    client = NS3ETLClient(config)
    
    # Start client services
    client.start_client()
    
    # Start WebSocket client
    websocket_task = asyncio.create_task(client.websocket_client())
    
    # Dashboard data endpoint (simple example)
    async def dashboard_server():
        while True:
            dashboard_data = client.get_dashboard_data()
            logger.info(f"Dashboard Update: {dashboard_data.get('metrics', {})}")
            await asyncio.sleep(10)  # Update every 10 seconds
    
    dashboard_task = asyncio.create_task(dashboard_server())
    
    try:
        await asyncio.gather(websocket_task, dashboard_task)
    except KeyboardInterrupt:
        logger.info("Client stopped by user")
        client.stop_client()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("ETL Client stopped")