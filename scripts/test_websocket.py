"""
WebSocket test client for the 5G Slicing Dashboard.

This script connects to the WebSocket server and tests basic functionality.
"""
import asyncio
import json
import uuid
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WebSocketTestClient:
    def __init__(self, url="ws://localhost:8000/ws/test-client"):
        self.url = url
        self.client_id = f"test-client-{str(uuid.uuid4())[:8]}"
        self.websocket = None
        self.running = False
    
    async def connect(self):
        """Connect to the WebSocket server."""
        import websockets
        self.websocket = await websockets.connect(f"{self.url}/{self.client_id}")
        logger.info(f"Connected to {self.url} as {self.client_id}")
        self.running = True
    
    async def send_message(self, message):
        """Send a message to the WebSocket server."""
        if not self.websocket:
            await self.connect()
        
        if isinstance(message, dict):
            message = json.dumps(message)
        
        await self.websocket.send(message)
        logger.info(f"Sent: {message}")
    
    async def receive_messages(self):
        """Continuously receive and log messages from the WebSocket server."""
        try:
            while self.running:
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    logger.info(f"Received: {message}")
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.error("Connection closed by server")
                    self.running = False
                    break
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")
            self.running = False
    
    async def subscribe(self, channels):
        """Subscribe to one or more channels."""
        if not isinstance(channels, list):
            channels = [channels]
        
        await self.send_message({
            "action": "subscribe",
            "channels": channels
        })
    
    async def unsubscribe(self, channels):
        """Unsubscribe from one or more channels."""
        if not isinstance(channels, list):
            channels = [channels]
        
        await self.send_message({
            "action": "unsubscribe",
            "channels": channels
        })
    
    async def ping(self):
        """Send a ping message."""
        await self.send_message({"action": "ping"})
    
    async def close(self):
        """Close the WebSocket connection."""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            logger.info("WebSocket connection closed")

async def run_test():
    """Run the WebSocket test."""
    client = WebSocketTestClient()
    
    try:
        # Connect to the WebSocket server
        await client.connect()
        
        # Start receiving messages in the background
        receive_task = asyncio.create_task(client.receive_messages())
        
        # Test subscriptions
        await client.subscribe(["dashboard"])
        await asyncio.sleep(1)
        
        # Test ping
        await client.ping()
        await asyncio.sleep(1)
        
        # Test unsubscribing
        await client.unsubscribe(["dashboard"])
        await asyncio.sleep(1)
        
        # Resubscribe for broadcast test
        await client.subscribe(["dashboard"])
        await asyncio.sleep(1)
        
        print("\nTest completed successfully!")
        print("Press Ctrl+C to exit...")
        
        # Keep the client running until interrupted
        while client.running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        # Clean up
        await client.close()
        if 'receive_task' in locals():
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass

if __name__ == "__main__":
    # Install websockets package if not available
    try:
        import websockets
    except ImportError:
        import sys
        import subprocess
        print("Installing required package: websockets")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
        import websockets
    
    # Run the test
    asyncio.run(run_test())
