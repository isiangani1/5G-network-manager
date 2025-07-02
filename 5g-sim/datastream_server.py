# ns3_stream_server.py - Ubuntu VM Side
import asyncio
import websockets
import json
import socket
import threading
import time
import queue
from datetime import datetime
from typing import Dict, List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NS3StreamServer:
    def __init__(self, config: Dict):
        self.config = config
        self.websocket_clients = set()
        self.tcp_clients = set()
        self.data_queue = queue.Queue(maxsize=10000)  # Buffer for high-throughput
        self.running = False
        
        # Statistics
        self.stats = {
            'packets_sent': 0,
            'clients_connected': 0,
            'last_activity': None
        }
    
    async def websocket_handler(self, websocket, path):
        """Handle WebSocket connections"""
        try:
            self.websocket_clients.add(websocket)
            self.stats['clients_connected'] += 1
            logger.info(f"WebSocket client connected. Total: {len(self.websocket_clients)}")
            
            # Send connection confirmation
            await websocket.send(json.dumps({
                'type': 'connection',
                'status': 'connected',
                'timestamp': datetime.now().isoformat()
            }))
            
            # Keep connection alive
            await websocket.wait_closed()
            
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket client disconnected")
        finally:
            self.websocket_clients.discard(websocket)
    
    def tcp_server_handler(self):
        """Handle TCP socket connections"""
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp_socket.bind((self.config['host'], self.config['tcp_port']))
        tcp_socket.listen(5)
        
        logger.info(f"TCP server listening on {self.config['host']}:{self.config['tcp_port']}")
        
        while self.running:
            try:
                client_socket, addr = tcp_socket.accept()
                self.tcp_clients.add(client_socket)
                logger.info(f"TCP client connected from {addr}")
                
                # Handle client in separate thread
                threading.Thread(
                    target=self.handle_tcp_client,
                    args=(client_socket, addr),
                    daemon=True
                ).start()
                
            except Exception as e:
                if self.running:
                    logger.error(f"TCP server error: {e}")
    
    def handle_tcp_client(self, client_socket, addr):
        """Handle individual TCP client"""
        try:
            while self.running:
                # Send keep-alive or wait for disconnection
                time.sleep(1)
        except Exception as e:
            logger.error(f"TCP client {addr} error: {e}")
        finally:
            self.tcp_clients.discard(client_socket)
            client_socket.close()
            logger.info(f"TCP client {addr} disconnected")
    
    def udp_sender(self):
        """UDP streaming handler"""
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        logger.info(f"UDP sender ready on port {self.config['udp_port']}")
        
        while self.running:
            try:
                if not self.data_queue.empty():
                    data = self.data_queue.get_nowait()
                    
                    # Send to all registered UDP clients
                    for client_addr in self.config.get('udp_clients', []):
                        try:
                            udp_socket.sendto(
                                json.dumps(data).encode('utf-8'),
                                (client_addr['host'], client_addr['port'])
                            )
                        except Exception as e:
                            logger.error(f"UDP send error to {client_addr}: {e}")
                
                time.sleep(0.001)  # 1ms delay
                
            except queue.Empty:
                time.sleep(0.01)
            except Exception as e:
                logger.error(f"UDP sender error: {e}")
        
        udp_socket.close()
    
    async def broadcast_data(self):
        """Broadcast data to all connected clients"""
        while self.running:
            try:
                if not self.data_queue.empty():
                    data = self.data_queue.get_nowait()
                    json_data = json.dumps(data)
                    
                    # WebSocket broadcast
                    if self.websocket_clients:
                        disconnected = set()
                        for websocket in self.websocket_clients.copy():
                            try:
                                await websocket.send(json_data)
                                self.stats['packets_sent'] += 1
                            except websockets.exceptions.ConnectionClosed:
                                disconnected.add(websocket)
                            except Exception as e:
                                logger.error(f"WebSocket send error: {e}")
                                disconnected.add(websocket)
                        
                        # Remove disconnected clients
                        self.websocket_clients -= disconnected
                    
                    # TCP broadcast
                    if self.tcp_clients:
                        disconnected = set()
                        for client_socket in self.tcp_clients.copy():
                            try:
                                client_socket.send((json_data + '\n').encode('utf-8'))
                            except Exception as e:
                                logger.error(f"TCP send error: {e}")
                                disconnected.add(client_socket)
                        
                        # Remove disconnected clients
                        self.tcp_clients -= disconnected
                    
                    self.stats['last_activity'] = datetime.now()
                
                await asyncio.sleep(0.001)  # 1ms delay for high throughput
                
            except queue.Empty:
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")
    
    def add_ns3_data(self, data: Dict):
        """Add NS-3 data to streaming queue"""
        try:
            # Add timestamp if not present
            if 'timestamp' not in data:
                data['timestamp'] = time.time()
            
            # Add to queue (non-blocking)
            if not self.data_queue.full():
                self.data_queue.put_nowait(data)
            else:
                # Queue full - drop oldest data
                try:
                    self.data_queue.get_nowait()
                    self.data_queue.put_nowait(data)
                    logger.warning("Data queue full - dropping old data")
                except queue.Empty:
                    pass
                    
        except Exception as e:
            logger.error(f"Error adding NS3 data: {e}")
    
    def get_stats(self) -> Dict:
        """Get server statistics"""
        return {
            **self.stats,
            'websocket_clients': len(self.websocket_clients),
            'tcp_clients': len(self.tcp_clients),
            'queue_size': self.data_queue.qsize(),
            'uptime': time.time() - self.start_time if hasattr(self, 'start_time') else 0
        }
    
    async def start_server(self):
        """Start all streaming services"""
        self.running = True
        self.start_time = time.time()
        
        logger.info("Starting NS3 Stream Server...")
        
        # Start WebSocket server
        websocket_server = websockets.serve(
            self.websocket_handler,
            self.config['host'],
            self.config['websocket_port']
        )
        
        # Start TCP server in thread
        tcp_thread = threading.Thread(target=self.tcp_server_handler, daemon=True)
        tcp_thread.start()
        
        # Start UDP sender in thread
        udp_thread = threading.Thread(target=self.udp_sender, daemon=True)
        udp_thread.start()
        
        # Start data broadcaster
        broadcast_task = asyncio.create_task(self.broadcast_data())
        
        logger.info(f"WebSocket server: ws://{self.config['host']}:{self.config['websocket_port']}")
        logger.info(f"TCP server: {self.config['host']}:{self.config['tcp_port']}")
        logger.info(f"UDP sender: port {self.config['udp_port']}")
        
        # Run servers
        await asyncio.gather(
            websocket_server,
            broadcast_task
        )
    
    def stop_server(self):
        """Stop all services"""
        self.running = False
        logger.info("Stopping NS3 Stream Server...")


# Example NS-3 Integration Class
class NS3DataCollector:
    def __init__(self, stream_server: NS3StreamServer):
        self.stream_server = stream_server
        self.node_stats = {}
    
    def on_packet_tx(self, node_id: int, packet_size: int, destination: str):
        """Called when NS-3 transmits a packet"""
        data = {
            'type': 'packet_tx',
            'node_id': node_id,
            'packet_size': packet_size,
            'destination': destination,
            'timestamp': time.time()
        }
        self.stream_server.add_ns3_data(data)
    
    def on_packet_rx(self, node_id: int, packet_size: int, source: str, delay: float):
        """Called when NS-3 receives a packet"""
        data = {
            'type': 'packet_rx',
            'node_id': node_id,
            'packet_size': packet_size,
            'source': source,
            'delay': delay,
            'timestamp': time.time()
        }
        self.stream_server.add_ns3_data(data)
    
    def on_throughput_update(self, node_id: int, throughput: float):
        """Called when throughput is calculated"""
        data = {
            'type': 'throughput',
            'node_id': node_id,
            'throughput_mbps': throughput,
            'timestamp': time.time()
        }
        self.stream_server.add_ns3_data(data)


# Configuration
def get_default_config():
    return {
        'host': '0.0.0.0',  # Listen on all interfaces
        'websocket_port': 8765,
        'tcp_port': 8766,
        'udp_port': 8767,
        'udp_clients': [
            {'host': '192.168.1.100', 'port': 9001}  # Windows ETL endpoint
        ]
    }


# Main execution
async def main():
    config = get_default_config()
    server = NS3StreamServer(config)
    
    # Example: Start server and simulate NS-3 data
    server_task = asyncio.create_task(server.start_server())
    
    # Simulate NS-3 data generation
    async def simulate_ns3_data():
        collector = NS3DataCollector(server)
        
        while True:
            # Simulate packet transmission
            collector.on_packet_tx(
                node_id=1,
                packet_size=1024,
                destination="10.1.1.2"
            )
            
            # Simulate throughput update
            collector.on_throughput_update(
                node_id=1,
                throughput=50.5
            )
            
            await asyncio.sleep(0.1)  # 100ms intervals
    
    # Run simulation alongside server
    await asyncio.gather(
        server_task,
        simulate_ns3_data()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")