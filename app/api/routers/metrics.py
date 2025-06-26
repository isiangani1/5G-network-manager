from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta
import random

router = APIRouter(
    prefix="/metrics",
    tags=["Metrics"],
    responses={404: {"description": "Not found"}},
)

def generate_metric_data():
    """Generate mock metric data"""
    now = datetime.utcnow()
    timestamps = [now - timedelta(minutes=i) for i in range(60)][::-1]
    return [
        {
            "timestamp": ts.isoformat(),
            "value": random.uniform(0, 100),
            "unit": "%"
        }
        for ts in timestamps
    ]

@router.get("/slices/{slice_id}")
async def get_slice_metrics(slice_id: str):
    """Get metrics for a specific slice"""
    return {
        "slice_id": slice_id,
        "metrics": {
            "latency": generate_metric_data(),
            "throughput": generate_metric_data(),
            "packet_loss": generate_metric_data(),
            "active_users": generate_metric_data()
        }
    }

@router.get("/devices/{device_id}")
async def get_device_metrics(device_id: str):
    """Get metrics for a specific device"""
    return {
        "device_id": device_id,
        "metrics": {
            "cpu_usage": generate_metric_data(),
            "memory_usage": generate_metric_data(),
            "network_throughput": generate_metric_data()
        }
    }
