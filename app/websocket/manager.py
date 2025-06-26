import asyncio
import json
import time
import uuid
from typing import Dict, Set, Optional, Any, List, Union
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class ConnectionInfo:
    """Class to track WebSocket connection information."""
    websocket: Any
    connected_at: datetime
    last_active: datetime
    client_id: str
    user_agent: Optional[str] = None
    remote_addr: Optional[str] = None

class WebSocketManager:
    def __init__(self):
        # Track active connections by channel
        self.active_connections: Dict[str, Dict[str, ConnectionInfo]] = {
            'metrics': {},
            'alerts': {},
            'slices': {}
        }
        # Cache for metrics data
        self.metrics_cache = {}
        self.last_updated = datetime.utcnow()
        # Connection statistics
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'messages_sent': 0,
            'messages_received': 0,
            'errors': 0
        }
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """Periodically clean up stale connections."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                await self.cleanup_stale_connections(timeout=300)  # 5 minutes timeout
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
    
    async def cleanup_stale_connections(self, timeout: int = 300):
        """Remove connections that haven't been active for the given timeout."""
        now = datetime.utcnow()
        stale = []
        
        for channel, connections in self.active_connections.items():
            for client_id, conn in list(connections.items()):
                if (now - conn.last_active).total_seconds() > timeout:
                    stale.append(connection_id)
        
        for connection_id in stale:
            await self.disconnect(connection_id=connection_id)
    
    async def connect(self, websocket: Any, channel: str, user_agent: str = None, remote_addr: str = None) -> str:
        """Register a WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            channel: The channel to subscribe to
            user_agent: The User-Agent header from the client
            remote_addr: The client's IP address
            
        Returns:
            str: The connection ID
            
        Raises:
            ValueError: If the channel is invalid
            RuntimeError: If the connection cannot be established
        """
        if not channel or not isinstance(channel, str):
            raise ValueError("Channel must be a non-empty string")
            
        connection_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        # Create connection info
        connection_info = ConnectionInfo(
            connection_id=connection_id,
            websocket=websocket,
            channel=channel,
            user_agent=user_agent or 'unknown',
            remote_addr=remote_addr or 'unknown',
            connected_at=now,
            last_active=now,
            message_count=0,
            status='connected'
        )
        
        # Store the connection
        async with self._lock:
            self._connections[connection_id] = connection_info
            
            # Add to channel subscriptions
            if channel not in self._channels:
                self._channels[channel] = set()
            self._channels[channel].add(connection_id)
        
        logger.info(
            f"New WebSocket connection: {connection_id} "
            f"on channel '{channel}' from {remote_addr} ({user_agent or 'unknown'})"
        )
        
        # Send initial data if available for this channel
        if channel == 'metrics' and self._cached_metrics:
            try:
                await self.send_message(
                    connection_id,
                    {
                        'type': 'initial_data',
                        'data': self._cached_metrics,
                        'timestamp': now.isoformat()
                    }
                )
                logger.debug(f"Sent initial data to new connection {connection_id}")
            except Exception as e:
                logger.warning(f"Failed to send initial data to {connection_id}: {str(e)}")
        
        return connection_id
    
    async def disconnect(self, websocket: Any = None, channel: str = None, connection_id: str = None) -> Dict:
        """Unregister a WebSocket connection.
        
        Args:
            websocket: The WebSocket connection (optional if connection_id is provided)
            channel: The channel to unsubscribe from (optional if connection_id is provided)
            connection_id: The ID of the connection to disconnect (optional)
            
        Returns:
            Dict: Information about the disconnected connection, or None if not found
            
        Raises:
            ValueError: If insufficient information is provided to identify the connection
        """
        connection_info = None
        
        async with self._lock:
            if connection_id:
                # Disconnect by connection ID
                connection_info = self._connections.pop(connection_id, None)
                if connection_info:
                    # Remove from channel subscriptions
                    channel = connection_info.channel
                    if channel in self._channels:
                        self._channels[channel].discard(connection_id)
                        if not self._channels[channel]:  # Remove empty channels
                            self._channels.pop(channel, None)
            elif websocket and channel:
                # Legacy disconnect by websocket and channel
                for conn_id, conn in list(self._connections.items()):
                    if conn.websocket == websocket and conn.channel == channel:
                        connection_info = self._connections.pop(conn_id, None)
                        # Remove from channel subscriptions
                        if channel in self._channels:
                            self._channels[channel].discard(conn_id)
                            if not self._channels[channel]:  # Remove empty channels
                                self._channels.pop(channel, None)
                        break
            else:
                raise ValueError("Must provide either connection_id or both websocket and channel")
        
        if connection_info:
            # Update connection info
            connection_info.status = 'disconnected'
            connection_info.disconnected_at = datetime.utcnow()
            
            # Log the disconnection
            logger.info(
                f"WebSocket disconnected: {connection_info.connection_id} "
                f"from channel '{connection_info.channel}' "
                f"(duration: {(connection_info.disconnected_at - connection_info.connected_at).total_seconds():.1f}s, "
                f"messages: {connection_info.message_count})"
            )
            
            # Clean up the WebSocket connection
            try:
                await websocket.close()
            except Exception as e:
                logger.debug(f"Error closing WebSocket: {str(e)}")
            
            return asdict(connection_info)
        
        return None
    
    async def broadcast(self, channel: str, message: Union[dict, str], exclude_client_id: str = None) -> int:
        """Send a message to all connected clients in a channel, optionally excluding a client."""
        if channel not in self._channels or not self._channels[channel]:
            return 0
            
        message_str = json.dumps(message, default=str) if isinstance(message, dict) else message
        disconnected = []
        sent_count = 0
        
        async with self._lock:
            for connection_id in list(self._channels[channel]):
                if exclude_client_id and connection_id == exclude_client_id:
                    continue
                
                try:
                    connection_info = self._connections[connection_id]
                    await connection_info.websocket.send_text(message_str)
                    connection_info.last_active = datetime.utcnow()
                    connection_info.message_count += 1
                    sent_count += 1
                    self.stats['messages_sent'] += 1
                except Exception as e:
                    logger.warning(f"Error sending to client {connection_id}: {e}")
                    disconnected.append(connection_id)
        
        # Clean up disconnected clients
        for connection_id in disconnected:
            await self.disconnect(connection_id=connection_id)
            
        return sent_count
    
    async def send_message(self, connection_id: str, message: dict) -> bool:
        """Send a message to a specific WebSocket connection."""
        try:
            connection_info = self._connections[connection_id]
            await connection_info.websocket.send_json(message)
            connection_info.last_active = datetime.utcnow()
            connection_info.message_count += 1
            self.stats['messages_sent'] += 1
            return True
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            self.stats['errors'] += 1
            return False
    
    def update_metrics_cache(self, metrics: dict):
        """Update the metrics cache."""
        self._cached_metrics = metrics
    
    async def broadcast_metrics(self, metrics_data: Dict[str, Any]) -> None:
        """Broadcast metrics data to all connected clients.
        
        Args:
            metrics_data: Dictionary containing metrics data to broadcast
            
        This method:
        1. Formats the metrics data for WebSocket transmission
        2. Updates the cached metrics data
        3. Broadcasts to all connected clients in the 'metrics' channel
        4. Handles any broadcast errors
        """
        if not metrics_data:
            logger.warning("No metrics data provided to broadcast")
            return
            
        try:
            # Prepare the message with metadata
            message = {
                'type': 'metrics_update',
                'timestamp': datetime.utcnow().isoformat(),
                'data': metrics_data,
                'metadata': {
                    'data_points': len(metrics_data.get('timestamps', [])),
                    'slices': list(set(metrics_data.get('slice_ids', []))),
                    'generated_at': datetime.utcnow().isoformat()
                }
            }
            
            # Update cached metrics
            self._cached_metrics = message
            
            # Broadcast to all connected clients in the metrics channel
            await self.broadcast('metrics', message)
            
            # Log the broadcast
            logger.debug(f"Broadcasted metrics update to {len(self._connections)} clients")
            
        except Exception as e:
            logger.error(f"Error broadcasting metrics: {str(e)}", exc_info=True)
            raise
    
    def get_connection_stats(self) -> dict:
        """Get current connection statistics."""
        return {
            **self.stats,
            'active_connections_by_channel': {
                channel: len(connections) 
                for channel, connections in self.active_connections.items()
            }
        }
    
    def get_active_connections(self) -> List[dict]:
        """Get information about all active connections."""
        connections = []
        for channel, conns in self.active_connections.items():
            for conn in conns.values():
                conn_dict = asdict(conn)
                conn_dict['channel'] = channel
                conn_dict.pop('websocket', None)  # Remove the actual websocket object
                connections.append(conn_dict)
        return connections

# Global WebSocket manager instance
websocket_manager = WebSocketManager()
