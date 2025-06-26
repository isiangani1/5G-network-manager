from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta
from typing import List, Dict, Any
import json

from app.db.database import get_db
from app.db.models import Slice, Metric, SliceKPI, Alert
from app.schemas.dashboard import (
    SliceMetricsResponse,
    KPIResponse,
    AlertResponse,
    TimeRange
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/slices/metrics", response_model=List[SliceMetricsResponse])
async def get_slice_metrics(
    time_range: TimeRange = TimeRange.last_hour,
    db: AsyncSession = Depends(get_db)
):
    """
    Get metrics for all slices within the specified time range.
    """
    # Calculate time filter based on the selected range
    now = datetime.utcnow()
    if time_range == TimeRange.last_hour:
        start_time = now - timedelta(hours=1)
    elif time_range == TimeRange.last_6_hours:
        start_time = now - timedelta(hours=6)
    else:  # last_24_hours
        start_time = now - timedelta(days=1)

    # Get latest metrics for each slice
    subq = (
        select(
            Metric.slice_id,
            func.max(Metric.timestamp).label("max_timestamp")
        )
        .where(Metric.timestamp >= start_time)
        .group_by(Metric.slice_id)
        .subquery()
    )

    query = (
        select(
            Slice.id,
            Slice.name,
            Metric.throughput,
            Metric.latency,
            Metric.packet_loss,
            Metric.timestamp
        )
        .join(subq, (Metric.slice_id == subq.c.slice_id) & 
                     (Metric.timestamp == subq.c.max_timestamp))
        .join(Slice, Slice.id == Metric.slice_id)
    )

    result = await db.execute(query)
    metrics = result.all()

    return [
        SliceMetricsResponse(
            slice_id=row.id,
            slice_name=row.name,
            throughput=row.throughput,
            latency=row.latency,
            packet_loss=row.packet_loss,
            timestamp=row.timestamp
        )
        for row in metrics
    ]

@router.get("/kpis", response_model=List[KPIResponse])
async def get_kpis(
    time_range: TimeRange = TimeRange.last_hour,
    db: AsyncSession = Depends(get_db)
):
    """
    Get KPIs for all slices within the specified time range.
    """
    # Calculate time filter based on the selected range
    now = datetime.utcnow()
    if time_range == TimeRange.last_hour:
        start_time = now - timedelta(hours=1)
    elif time_range == TimeRange.last_6_hours:
        start_time = now - timedelta(hours=6)
    else:  # last_24_hours
        start_time = now - timedelta(days=1)

    # Get latest KPIs for each slice
    subq = (
        select(
            SliceKPI.slice_id,
            func.max(SliceKPI.timestamp).label("max_timestamp")
        )
        .where(SliceKPI.timestamp >= start_time)
        .group_by(SliceKPI.slice_id)
        .subquery()
    )

    query = (
        select(
            SliceKPI,
            Slice.name.label("slice_name")
        )
        .join(subq, (SliceKPI.slice_id == subq.c.slice_id) & 
                     (SliceKPI.timestamp == subq.c.max_timestamp))
        .join(Slice, Slice.id == SliceKPI.slice_id)
    )

    result = await db.execute(query)
    kpis = result.all()

    return [
        KPIResponse(
            slice_id=row.SliceKPI.slice_id,
            slice_name=row.slice_name,
            latency=row.SliceKPI.latency,
            throughput=row.SliceKPI.throughput,
            connected_devices=row.SliceKPI.connected_devices,
            packet_loss=row.SliceKPI.packet_loss,
            availability=row.SliceKPI.availability,
            timestamp=row.SliceKPI.timestamp
        )
        for row in kpis
    ]

@router.get("/alerts", response_model=List[AlertResponse])
async def get_active_alerts(
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """
    Get active alerts.
    """
    query = (
        select(Alert)
        .where(Alert.resolved == False)
        .order_by(desc(Alert.timestamp))
        .limit(limit)
    )
    
    result = await db.execute(query)
    alerts = result.scalars().all()

    return [
        AlertResponse(
            id=alert.id,
            level=alert.level,
            message=alert.message,
            entity_type=alert.entity_type,
            entity_id=alert.entity_id,
            timestamp=alert.timestamp,
            context=alert.context
        )
        for alert in alerts
    ]

@router.get("/slices/{slice_id}/history", response_model=List[Dict[str, Any]])
async def get_slice_history(
    slice_id: str,
    time_range: TimeRange = TimeRange.last_hour,
    db: AsyncSession = Depends(get_db)
):
    """
    Get historical metrics for a specific slice.
    """
    # Calculate time filter based on the selected range
    now = datetime.utcnow()
    if time_range == TimeRange.last_hour:
        start_time = now - timedelta(hours=1)
    elif time_range == TimeRange.last_6_hours:
        start_time = now - timedelta(hours=6)
    else:  # last_24_hours
        start_time = now - timedelta(days=1)

    query = (
        select(
            Metric.timestamp,
            Metric.throughput,
            Metric.latency,
            Metric.packet_loss
        )
        .where(
            (Metric.slice_id == slice_id) &
            (Metric.timestamp >= start_time)
        )
        .order_by(Metric.timestamp)
    )

    result = await db.execute(query)
    metrics = result.all()

    return [{
        "timestamp": row.timestamp.isoformat(),
        "throughput": row.throughput,
        "latency": row.latency,
        "packet_loss": row.packet_loss
    } for row in metrics]
