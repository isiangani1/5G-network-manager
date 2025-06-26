from datetime import datetime, timedelta
from typing import Dict, List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.db.database import get_db
from app.db.models import Slice, Device, Metric, Alert, User
from app.core.security import get_current_active_user

router = APIRouter()

@router.get("/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get dashboard statistics for the authenticated user.
    """
    try:
        # Get current time and time 24 hours ago
        now = datetime.utcnow()
        one_day_ago = now - timedelta(days=1)
        
        # Get active slices count
        active_slices = db.query(Slice).filter(
            Slice.status == "active"
        ).count()
        
        # Get connected devices count
        connected_devices = db.query(Device).filter(
            Device.status == "connected"
        ).count()
        
        # Get active alerts count
        active_alerts = db.query(Alert).filter(
            Alert.status == "active"
        ).count()
        
        # Get average throughput from metrics
        avg_throughput = db.query(
            func.avg(Metric.throughput).label('avg_throughput')
        ).filter(
            Metric.timestamp >= one_day_ago
        ).scalar() or 0
        
        # Get recent metrics for the chart (last 24 hours, grouped by hour)
        metrics = db.query(
            func.date_trunc('hour', Metric.timestamp).label('hour'),
            func.avg(Metric.throughput).label('avg_throughput'),
            func.avg(Metric.latency).label('avg_latency'),
            func.avg(Metric.packet_loss).label('avg_packet_loss')
        ).filter(
            Metric.timestamp >= one_day_ago
        ).group_by(
            'hour'
        ).order_by('hour').all()
        
        # Get slice distribution
        slice_distribution = db.query(
            Slice.name,
            func.count(Device.id).label('device_count')
        ).join(
            Device, Device.slice_id == Slice.id
        ).group_by(
            Slice.name
        ).all()
        
        # Get recent activity
        recent_activity = db.query(Alert).order_by(
            Alert.timestamp.desc()
        ).limit(10).all()
        
        # Format the response
        return {
            "active_slices": active_slices,
            "connected_devices": connected_devices,
            "active_alerts": active_alerts,
            "avg_throughput": round(float(avg_throughput), 2),
            "metrics": [{
                "hour": m.hour.isoformat() if m.hour else None,
                "avg_throughput": float(m.avg_throughput or 0),
                "avg_latency": float(m.avg_latency or 0),
                "avg_packet_loss": float(m.avg_packet_loss or 0)
            } for m in metrics],
            "slice_distribution": [{
                "name": s.name,
                "device_count": s.device_count
            } for s in slice_distribution],
            "recent_activity": [{
                "id": a.id,
                "timestamp": a.timestamp.isoformat(),
                "severity": a.severity,
                "message": a.message,
                "status": a.status,
                "slice_id": a.slice_id
            } for a in recent_activity]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching dashboard data: {str(e)}"
        )
