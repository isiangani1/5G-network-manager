"""Test NS-3 client for sending simulated KPI data to the 5G Slicing Manager"""
import asyncio
import json
import random
import logging
from datetime import datetime, timedelta
import argparse
import aiohttp
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NS3TestClient:
    """Test client that simulates an NS-3 instance sending KPI data"""
    
    def __init__(self, api_url: str = "http://localhost:8000", ws_url: str = "ws://localhost:8000"):
        self.api_url = api_url.rstrip('/')
        self.ws_url = ws_url.rstrip('/')
        self.session = None
        self.ws = None
        self.running = False
    
    async def connect(self):
        """Initialize HTTP and WebSocket sessions"""
        self.session = aiohttp.ClientSession()
        logger.info(f"Connected to API at {self.api_url}")
    
    async def close(self):
        """Close all connections"""
        if self.ws:
            await self.ws.close()
            self.ws = None
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("Closed all connections")
    
    async def create_test_slice(self) -> Dict[str, Any]:
        """Create a test slice for simulation"""
        slice_data = {
            "name": "Test Slice",
            "description": "Test slice for NS-3 simulation",
            "priority": 5
        }
        
        try:
            async with self.session.post(
                f"{self.api_url}/api/slices/",
                json=slice_data
            ) as response:
                if response.status == 201:
                    data = await response.json()
                    logger.info(f"Created test slice: {data['slice_id']}")
                    return data
                else:
                    error = await response.text()
                    logger.error(f"Failed to create slice: {error}")
                    return None
        except Exception as e:
            logger.error(f"Error creating slice: {e}")
            return None
    
    async def get_slice_config(self, slice_id: str) -> Dict[str, Any]:
        """Get current configuration for a slice"""
        try:
            async with self.session.get(
                f"{self.api_url}/api/ns3/slices/{slice_id}/config"
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error = await response.text()
                    logger.error(f"Failed to get slice config: {error}")
                    return None
        except Exception as e:
            logger.error(f"Error getting slice config: {e}")
            return None
    
    async def send_kpi_data(self, slice_id: str, kpi_data: Dict[str, Any]) -> bool:
        """Send KPI data for a slice"""
        try:
            async with self.session.post(
                f"{self.api_url}/api/slices/{slice_id}/kpis",
                json=kpi_data
            ) as response:
                if response.status == 201:
                    return True
                else:
                    error = await response.text()
                    logger.error(f"Failed to send KPI data: {error}")
                    return False
        except Exception as e:
            logger.error(f"Error sending KPI data: {e}")
            return False
    
    async def simulate_kpi_data(self, slice_id: str, duration: int = 300, interval: float = 1.0):
        """Simulate KPI data for a slice"""
        self.running = True
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(seconds=duration)
        
        logger.info(f"Starting KPI simulation for slice {slice_id} for {duration} seconds")
        
        while self.running and datetime.utcnow() < end_time:
            try:
                # Generate random KPI data
                kpi_data = {
                    "latency_ms": random.uniform(5.0, 150.0),  # 5-150ms
                    "jitter_ms": random.uniform(0.1, 10.0),    # 0.1-10ms
                    "throughput_mbps": random.uniform(50.0, 1000.0),  # 50-1000 Mbps
                    "packet_loss_rate": random.uniform(0.0001, 0.05),  # 0.01%-5%
                    "sla_breach": random.random() < 0.1  # 10% chance of SLA breach
                }
                
                # Send KPI data
                success = await self.send_kpi_data(slice_id, kpi_data)
                if success:
                    logger.debug(f"Sent KPI data for slice {slice_id}: {kpi_data}")
                
                # Wait for next interval
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                logger.info("KPI simulation cancelled")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in KPI simulation: {e}")
                await asyncio.sleep(1)  # Wait a bit before retrying
        
        logger.info("KPI simulation completed")

async def main():
    parser = argparse.ArgumentParser(description="NS-3 Test Client for 5G Slicing Manager")
    parser.add_argument("--api-url", default="http://localhost:8000", help="Base URL of the API")
    parser.add_argument("--ws-url", default="ws://localhost:8000", help="WebSocket URL")
    parser.add_argument("--duration", type=int, default=300, help="Simulation duration in seconds")
    parser.add_argument("--interval", type=float, default=1.0, help="Interval between KPI updates in seconds")
    
    args = parser.parse_args()
    
    client = NS3TestClient(api_url=args.api_url, ws_url=args.ws_url)
    
    try:
        # Connect to the API
        await client.connect()
        
        # Create a test slice
        slice_data = await client.create_test_slice()
        if not slice_data:
            logger.error("Failed to create test slice")
            return
        
        slice_id = slice_data['slice_id']
        
        # Get slice config
        config = await client.get_slice_config(slice_id)
        if config:
            logger.info(f"Slice config: {config}")
        
        # Start KPI simulation
        await client.simulate_kpi_data(slice_id, duration=args.duration, interval=args.interval)
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
