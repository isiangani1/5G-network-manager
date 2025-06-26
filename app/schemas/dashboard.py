from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class TimeRange(str, Enum):
    last_hour = "last_hour"
    last_6_hours = "last_6_hours"
    last_24_hours = "last_24_hours"

class SliceMetricsResponse(BaseModel):
    """Response model for slice metrics."""
    slice_id: str
    slice_name: str
    throughput: Optional[float] = None
    latency: Optional[float] = None
    packet_loss: Optional[float] = None
    timestamp: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class KPIResponse(BaseModel):
    """Response model for slice KPIs."""
    slice_id: str
    slice_name: str
    latency: Optional[float] = None
    throughput: Optional[float] = None
    connected_devices: int = 0
    packet_loss: Optional[float] = None
    availability: Optional[float] = None
    timestamp: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class AlertResponse(BaseModel):
    """Response model for alerts."""
    id: int
    level: str
    message: str
    entity_type: str
    entity_id: str
    timestamp: datetime
    context: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class SystemHealthResponse(BaseModel):
    """Response model for system health status."""
    status: str
    timestamp: datetime
    components: Dict[str, str]
    metrics: Dict[str, float]

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
