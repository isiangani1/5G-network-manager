"""
WebSocket client for streaming data from NS3 simulation.

This module provides a WebSocket client that connects to the NS3 simulation,
handles reconnections, and streams data to the ETL pipeline.
"""

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, Optional, Union

import aiohttp
import websockets
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import (
    ConnectionClosedError,
    ConnectionClosedOK,
    WebSocketException,
)

from app.core.config import settings
from app.core.error_handling import async_retry, DeadLetterQueue
from app.core.batch_processor import BatchProcessor

logger = logging.getLogger(__name__)


class WebSocketClient:
    """WebSocket client for streaming data from NS3 simulation."""

    def __init__(
        self,
        url: str,
        on_message: Callable[[Dict[str, Any]], None],
        on_error: Optional[Callable[[Exception], None]] = None,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
        reconnect_interval: int = 5,
        max_reconnect_attempts: int = 10,
        batch_size: int = 100,
        max_batch_wait: float = 1.0,
    ):
        """Initialize the WebSocket client.

        Args:
            url: WebSocket server URL
            on_message: Callback for processing received messages
            on_error: Callback for handling errors
            on_connect: Callback when connection is established
            on_disconnect: Callback when connection is closed
            reconnect_interval: Seconds between reconnection attempts
            max_reconnect_attempts: Maximum number of reconnection attempts
            batch_size: Number of messages to batch before processing
            max_batch_wait: Maximum seconds to wait before processing a partial batch
        """
        self.url = url
        self.on_message = on_message
        self.on_error = on_error or self._default_error_handler
        self.on_connect = on_connect or (lambda: None)
        self.on_disconnect = on_disconnect or (lambda: None)
        self.reconnect_interval = reconnect_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_attempts = 0
        self.running = False
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.dlq = DeadLetterQueue()
        
        # Initialize batch processor
        self.batch_processor = BatchProcessor(
            process_batch=self._process_message_batch,
            batch_size=batch_size,
            max_wait_seconds=max_batch_wait,
        )

    async def connect(self) -> None:
        """Connect to the WebSocket server."""
        if self.running:
            logger.warning("WebSocket client is already running")
            return

        self.running = True
        self.session = aiohttp.ClientSession()
        
        # Start the batch processor
        await self.batch_processor.start()
        
        # Start the connection loop
        asyncio.create_task(self._connection_loop())

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        self.running = False
        
        # Stop the batch processor
        await self.batch_processor.stop()
        
        # Close the WebSocket connection
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        
        # Close the session
        if self.session:
            await self.session.close()
            self.session = None
        
        self.on_disconnect()

    async def _connection_loop(self) -> None:
        """Main connection loop with reconnection logic."""
        while self.running:
            try:
                # Connect to the WebSocket server
                async with websockets.connect(
                    self.url,
                    ping_interval=settings.WEBSOCKET_PING_INTERVAL,
                    ping_timeout=settings.WEBSOCKET_PING_TIMEOUT,
                    close_timeout=1,
                    extra_headers={"User-Agent": "5G-Slice-Manager/1.0"},
                ) as websocket:
                    self.websocket = websocket
                    self.reconnect_attempts = 0
                    logger.info(f"Connected to WebSocket server at {self.url}")
                    self.on_connect()

                    # Process messages
                    await self._message_loop()

            except (ConnectionClosedError, ConnectionClosedOK) as e:
                logger.warning(f"WebSocket connection closed: {e}")
            except WebSocketException as e:
                logger.error(f"WebSocket error: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Unexpected error in WebSocket client: {e}", exc_info=True)
            
            # Handle reconnection
            if self.running:
                await self._handle_reconnect()
            
            # Small delay before reconnecting
            await asyncio.sleep(1)

    async def _message_loop(self) -> None:
        """Process incoming WebSocket messages."""
        if not self.websocket:
            raise RuntimeError("WebSocket connection not established")
        
        while self.running and self.websocket:
            try:
                message = await self.websocket.recv()
                await self._handle_message(message)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.on_error(e)
                break

    async def _handle_message(self, message: Union[str, bytes]) -> None:
        """Handle an incoming WebSocket message.
        
        Args:
            message: The received message (string or bytes)
        """
        try:
            # Parse JSON message
            if isinstance(message, bytes):
                message = message.decode("utf-8")
            
            data = json.loads(message)
            
            # Add to batch processor
            await self.batch_processor.add_item(data)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
            await self.dlq.put(message, e, {"type": "json_parse_error"})
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            await self.dlq.put(message, e, {"type": "processing_error"})
    
    async def _process_message_batch(self, batch: list) -> None:
        """Process a batch of messages.
        
        Args:
            batch: List of messages to process
        """
        for message in batch:
            try:
                self.on_message(message)
            except Exception as e:
                logger.error(f"Error in message handler: {e}", exc_info=True)
                await self.dlq.put(message, e, {"type": "handler_error"})

    async def _handle_reconnect(self) -> None:
        """Handle reconnection logic."""
        self.reconnect_attempts += 1
        
        if self.reconnect_attempts > self.max_reconnect_attempts > 0:
            logger.error("Max reconnection attempts reached, giving up")
            self.running = False
            return
        
        # Exponential backoff with jitter
        delay = min(
            self.reconnect_interval * (2 ** (self.reconnect_attempts - 1)),
            300,  # 5 minutes max delay
        )
        jitter = delay * 0.1 * (0.5 + (hash(str(time.time())) % 100) / 100.0)
        delay = min(delay + jitter, 300)
        
        logger.info(f"Reconnecting in {delay:.1f} seconds (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts or '∞'})")
        await asyncio.sleep(delay)

    def _default_error_handler(self, error: Exception) -> None:
        """Default error handler that logs the error."""
        logger.error(f"WebSocket error: {error}", exc_info=True)

    async def send_message(self, message: Union[dict, str, bytes]) -> None:
        """Send a message to the WebSocket server.
        
        Args:
            message: Message to send (dict will be JSON-serialized)
        """
        if not self.websocket:
            raise RuntimeError("WebSocket connection not established")
        
        try:
            if isinstance(message, dict):
                message = json.dumps(message)
            
            await self.websocket.send(message)
        except Exception as e:
            logger.error(f"Failed to send message: {e}", exc_info=True)
            raise

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()


# Example usage
if __name__ == "__main__":
    import asyncio
    import logging
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    async def on_message(message: dict) -> None:
        print(f"Received message: {message}")
    
    async def main():
        client = WebSocketClient(
            url="ws://localhost:8765",
            on_message=on_message,
            batch_size=10,
            max_batch_wait=0.5,
        )
        
        try:
            await client.connect()
            await asyncio.sleep(60)  # Run for 60 seconds
        except KeyboardInterrupt:
            pass
        finally:
            await client.disconnect()
    
    asyncio.run(main())
