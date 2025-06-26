"""
WebSocket manager for real-time updates in the 5G Slicing Dashboard.
"""
from typing import Dict, Set, Any, Optional, Union, List, TypeVar, Generic, Type, Callable, Awaitable
import asyncio
import json
import logging
from datetime import datetime
from enum import Enum
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EventType(str, Enum):
    """Types of events that can be sent through WebSocket."""
    SLICE_CREATED = "slice_created"
    SLICE_UPDATED = "slice_updated"
    SLICE_DELETED = "slice_deleted"
    METRICS_UPDATE = "metrics_update"
    ALERT = "alert"
    SYSTEM_NOTIFICATION = "system_notification"

class WebSocketMessage(BaseModel):
    """Base WebSocket message model."""
    event_type: EventType = Field(..., description="Type of the event")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event payload")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class ConnectionManager:
    """Manages active WebSocket connections."""
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "dashboard": set(),
            "slice_updates": set(),
            "kpi_updates": set(),
            "alerts": set()
        }
        self.lock = asyncio.Lock()
        self.subscriptions: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket, client_id: str, channels: List[str] = None):
        """Accept a new WebSocket connection and subscribe to specified channels."""
        await websocket.accept()
        channels = channels or ["dashboard"]
        
        async with self.lock:
            for channel in channels:
                if channel not in self.active_connections:
                    self.active_connections[channel] = set()
                self.active_connections[channel].add(websocket)
            
            # Track channel subscriptions per connection
            self.subscriptions[websocket] = set(channels)
            
        logger.info(f"Client {client_id} connected to channels: {', '.join(channels)}")
        return client_id

    async def disconnect(self, websocket: WebSocket, client_id: str):
        """Remove a WebSocket connection from all channels."""
        async with self.lock:
            # Remove from all channels
            for channel in self.active_connections.values():
                if websocket in channel:
                    channel.remove(websocket)
            
            # Remove subscription tracking
            if websocket in self.subscriptions:
                del self.subscriptions[websocket]
                
        logger.info(f"Client {client_id} disconnected")

    async def subscribe(self, websocket: WebSocket, channel: str) -> bool:
        """Subscribe a connection to a specific channel."""
        async with self.lock:
            if channel not in self.active_connections:
                self.active_connections[channel] = set()
            
            if websocket not in self.active_connections[channel]:
                self.active_connections[channel].add(websocket)
                self.subscriptions[websocket].add(channel)
                return True
            return False

    async def unsubscribe(self, websocket: WebSocket, channel: str) -> bool:
        """Unsubscribe a connection from a specific channel."""
        async with self.lock:
            if channel in self.active_connections and websocket in self.active_connections[channel]:
                self.active_connections[channel].remove(websocket)
                if websocket in self.subscriptions and channel in self.subscriptions[websocket]:
                    self.subscriptions[websocket].remove(channel)
                return True
            return False

    async def broadcast(self, channel: str, message: Union[dict, WebSocketMessage]):
        """
        Broadcast a message to all connections in the specified channel.
        
        Args:
            channel: The channel to broadcast to
            message: Either a dictionary or WebSocketMessage instance
        """
        if channel not in self.active_connections:
            logger.warning(f"Attempted to broadcast to non-existent channel: {channel}")
            return

        # Convert message to string if it's a WebSocketMessage
        if isinstance(message, WebSocketMessage):
            message_str = message.json()
        else:
            message_str = json.dumps(message)

        disconnected = set()
        
        async with self.lock:
            connections = list(self.active_connections[channel])
            
        for connection in connections:
            try:
                await connection.send_text(message_str)
            except (WebSocketDisconnect, RuntimeError) as e:
                logger.warning(f"Error sending to client: {e}")
                disconnected.add(connection)
            except Exception as e:
                logger.error(f"Unexpected error broadcasting to client: {e}", exc_info=True)
                disconnected.add(connection)
        
        # Clean up disconnected clients
        if disconnected:
            async with self.lock:
                for conn in disconnected:
                    for channel_set in self.active_connections.values():
                        if conn in channel_set:
                            channel_set.remove(conn)
                    if conn in self.subscriptions:
                        del self.subscriptions[conn]

    async def send_personal_message(self, websocket: WebSocket, message: Union[dict, WebSocketMessage]):
        """Send a message to a specific WebSocket connection."""
        try:
            if isinstance(message, WebSocketMessage):
                await websocket.send_text(message.json())
            else:
                await websocket.send_text(json.dumps(message))
        except (WebSocketDisconnect, RuntimeError) as e:
            logger.warning(f"Error sending personal message: {e}")
            await self.disconnect(websocket, "unknown")
        except Exception as e:
            logger.error(f"Unexpected error sending personal message: {e}", exc_info=True)

# Global WebSocket manager instance
websocket_manager = ConnectionManager()

def create_websocket_message(event_type: EventType, data: Dict[str, Any] = None) -> WebSocketMessage:
    """Helper function to create a WebSocket message."""
    return WebSocketMessage(event_type=event_type, data=data or {})
