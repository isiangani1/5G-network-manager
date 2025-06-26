"""
Database utility functions for the dashboard.
"""
__all__ = [
    'get_session',
    'check_database',
    'get_slices_with_device_counts',
    'get_slice_metrics',
    'get_slice_details',
    'get_alerts',
    'get_alert_by_id',
    'create_alert',
    'update_alert',
    'delete_alert',
    'get_device_by_id',
    'create_device',
    'update_device',
    'delete_device',
    'get_slice_kpis',
    'get_kpi_by_id',
    'create_kpi',
    'update_kpi',
    'delete_kpi',
    'get_metric_by_id',
    'create_metric',
    'update_metric',
    'delete_metric',
    'get_device_metrics',
    'get_slice_by_id',
    'create_slice',
    'update_slice',
    'delete_slice'
]

import logging
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text, func, and_, or_
from datetime import datetime, timedelta

# Import database models
from app.db.models import Slice, Device, SliceKPI, Alert, Metric

# Configure logging
logger = logging.getLogger(__name__)

# Create a new async session for each operation
async def get_session():
    """Create a new async session."""
    from app.db.database import async_session as async_session_factory
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def check_database():
    """Check database connection, tables, and data."""
    try:
        # Get a new session
        session_gen = get_session()
        session = await session_gen.__anext__()
        
        try:
            # Test connection
            result = await session.execute(text("SELECT 1"))
            test_value = result.scalar()
            
            if test_value != 1:
                return {
                    "status": "error",
                    "message": "Database connection test failed - unexpected result"
                }
            
            # Get table counts using SQLAlchemy Core
            tables = ["slices", "devices", "slice_kpis"]
            counts = {}
            
            for table in tables:
                try:
                    result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    counts[table] = result.scalar()
                except Exception as e:
                    counts[table] = f"Error: {str(e)}"
            
            return {
                "status": "success",
                "message": "Database connection successful",
                "table_counts": counts
            }
            
        except Exception as e:
            logger.error(f"Database check failed: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": f"Database connection failed: {str(e)}"
            }
        finally:
            await session.close()
    except Exception as e:
        logger.error(f"Failed to create database session: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to create database session: {str(e)}"
        }

async def get_slices_with_device_counts(session: AsyncSession) -> List[Dict[str, Any]]:
    """
    Get all slices with their device counts and KPI summaries using SQLAlchemy Core.
    """
    try:
        # Get slices with device counts using a single query with JOIN and GROUP BY
        slices_query = text("""
        SELECT 
            s.id, 
            s.name, 
            s.status, 
            s.description,
            s.created_at,
            s.updated_at,
            COUNT(d.id) as device_count,
            COALESCE(AVG(k.latency), 0) as avg_latency,
            COALESCE(AVG(k.throughput), 0) as avg_throughput,
            COALESCE(AVG(k.packet_loss), 0) as avg_packet_loss,
            COUNT(DISTINCT k.id) as kpi_count
        FROM slices s
        LEFT JOIN devices d ON s.id = d.slice_id
        LEFT JOIN slice_kpis k ON s.id = k.slice_id
        GROUP BY s.id, s.name, s.status, s.description, s.created_at, s.updated_at
        ORDER BY s.created_at DESC
        """)
        
        result = await session.execute(slices_query)
        slices = []
        
        for row in result.mappings():
            slice_data = dict(row)
            # Convert decimal.Decimal to float for JSON serialization
            slice_data.update({
                'avg_latency': float(slice_data['avg_latency']) if slice_data['avg_latency'] is not None else None,
                'avg_throughput': float(slice_data['avg_throughput']) if slice_data['avg_throughput'] is not None else None,
                'avg_packet_loss': float(slice_data['avg_packet_loss']) if slice_data['avg_packet_loss'] is not None else None,
                'device_count': int(slice_data['device_count']),
                'kpi_count': int(slice_data['kpi_count'])
            })
            slices.append(slice_data)
        
        return slices
        
    except Exception as e:
        logger.error(f"Error getting slices with device counts: {str(e)}", exc_info=True)
        raise


async def get_slice_metrics(session: AsyncSession, time_range: str = '1h', slice_id: int = None):
    """
    Get aggregated metrics for slices.
    
    Args:
        session: Database session
        time_range: Time range for metrics ('1h', '24h', '7d', '30d')
        slice_id: Optional slice ID to filter by
        
    Returns:
        Dict containing aggregated metrics
    """
    try:
        # Calculate time filter based on time_range
        now = datetime.utcnow()
        if time_range == '1h':
            time_filter = now - timedelta(hours=1)
        elif time_range == '24h':
            time_filter = now - timedelta(days=1)
        elif time_range == '7d':
            time_filter = now - timedelta(days=7)
        elif time_range == '30d':
            time_filter = now - timedelta(days=30)
        else:
            time_filter = now - timedelta(hours=1)  # Default to 1 hour
            
        # Build the base query
        query = select(
            Slice.id.label('slice_id'),
            Slice.name.label('slice_name'),
            func.avg(SliceKPI.latency).label('avg_latency'),
            func.avg(SliceKPI.throughput).label('avg_throughput'),
            func.avg(SliceKPI.packet_loss).label('avg_packet_loss'),
            func.avg(SliceKPI.connected_devices).label('avg_connected_devices'),
            func.count(SliceKPI.id).label('data_points')
        ).join(
            Slice, Slice.id == SliceKPI.slice_id
        ).filter(
            SliceKPI.timestamp >= time_filter
        ).group_by(
            Slice.id, Slice.name
        )
        
        # Add slice filter if provided
        if slice_id is not None:
            query = query.filter(SliceKPI.slice_id == slice_id)
            
        # Execute the query
        result = await session.execute(query)
        metrics = result.all()
        
        # Format the response
        return {
            'time_range': time_range,
            'time_from': time_filter.isoformat(),
            'time_to': now.isoformat(),
            'slices': [
                {
                    'slice_id': m.slice_id,
                    'slice_name': m.slice_name,
                    'avg_latency': float(m.avg_latency) if m.avg_latency else 0.0,
                    'avg_throughput': float(m.avg_throughput) if m.avg_throughput else 0.0,
                    'avg_packet_loss': float(m.avg_packet_loss) if m.avg_packet_loss else 0.0,
                    'avg_connected_devices': int(m.avg_connected_devices) if m.avg_connected_devices else 0,
                    'data_points': m.data_points
                }
                for m in metrics
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting slice metrics: {str(e)}", exc_info=True)
        raise

async def get_slice_details(session: AsyncSession, slice_id: int):
    """
    Get detailed information about a specific slice including devices and KPIs.
    """
    try:
        # Get slice details
        result = await session.execute(
            select(Slice).filter(Slice.id == slice_id)
        )
        slice_record = result.scalars().first()
        
        if not slice_record:
            return None
            
        # Get device count for this slice
        device_count = await session.execute(
            select(func.count(Device.id)).filter(Device.slice_id == slice_id)
        )
        device_count = device_count.scalar()
        
        # Get KPI summary for this slice
        kpi_summary = await session.execute(
            select(
                func.avg(SliceKPI.latency).label('avg_latency'),
                func.avg(SliceKPI.throughput).label('avg_throughput'),
                func.avg(SliceKPI.packet_loss).label('avg_packet_loss'),
                func.max(SliceKPI.timestamp).label('last_updated')
            ).filter(SliceKPI.slice_id == slice_id)
        )
        kpi_summary = kpi_summary.first()
        
        # Get recent KPI data points for charts
        recent_kpis = await session.execute(
            select(SliceKPI)
            .filter(SliceKPI.slice_id == slice_id)
            .order_by(SliceKPI.timestamp.desc())
            .limit(50)  # Get last 50 data points
        )
        recent_kpis = recent_kpis.scalars().all()
        
        # Format the response
        return {
            'id': slice_record.id,
            'name': slice_record.name,
            'description': slice_record.description,
            'status': slice_record.status,
            'created_at': slice_record.created_at.isoformat(),
            'updated_at': slice_record.updated_at.isoformat() if slice_record.updated_at else None,
            'device_count': device_count,
            'kpi_summary': {
                'avg_latency': float(kpi_summary.avg_latency) if kpi_summary.avg_latency else 0.0,
                'avg_throughput': float(kpi_summary.avg_throughput) if kpi_summary.avg_throughput else 0.0,
                'avg_packet_loss': float(kpi_summary.avg_packet_loss) if kpi_summary.avg_packet_loss else 0.0,
                'last_updated': kpi_summary.last_updated.isoformat() if kpi_summary and kpi_summary.last_updated else None
            },
            'recent_kpis': [
                {
                    'timestamp': kpi.timestamp.isoformat(),
                    'latency': float(kpi.latency) if kpi.latency else 0.0,
                    'throughput': float(kpi.throughput) if kpi.throughput else 0.0,
                    'packet_loss': float(kpi.packet_loss) if kpi.packet_loss else 0.0,
                    'connected_devices': kpi.connected_devices or 0
                }
                for kpi in recent_kpis
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting slice details: {str(e)}", exc_info=True)
        raise
        await session.close()

# Alerts functions
async def get_alerts(session: AsyncSession, limit: int = 10, status: str = None):
    """
    Get alerts with optional filtering.
    
    Args:
        session: Database session
        limit: Maximum number of alerts to return
        status: Filter by status (e.g., 'open', 'closed')
        
    Returns:
        List of alert dictionaries
    """
    try:
        query = select(Alert).order_by(Alert.created_at.desc())
        
        if status:
            query = query.filter(Alert.status == status)
            
        if limit:
            query = query.limit(limit)
            
        result = await session.execute(query)
        alerts = result.scalars().all()
        
        return [
            {
                'id': alert.id,
                'title': alert.title,
                'message': alert.message,
                'severity': alert.severity,
                'status': alert.status,
                'created_at': alert.created_at.isoformat(),
                'resolved_at': alert.resolved_at.isoformat() if alert.resolved_at else None
            }
            for alert in alerts
        ]
        
    except Exception as e:
        logger.error(f"Error getting alerts: {str(e)}", exc_info=True)
        raise

async def get_alert_by_id(session: AsyncSession, alert_id: int):
    """Get a single alert by ID."""
    try:
        result = await session.execute(
            select(Alert).filter(Alert.id == alert_id)
        )
        alert = result.scalars().first()
        
        if not alert:
            return None
            
        return {
            'id': alert.id,
            'title': alert.title,
            'message': alert.message,
            'severity': alert.severity,
            'status': alert.status,
            'created_at': alert.created_at.isoformat(),
            'resolved_at': alert.resolved_at.isoformat() if alert.resolved_at else None
        }
        
    except Exception as e:
        logger.error(f"Error getting alert {alert_id}: {str(e)}", exc_info=True)
        raise

async def create_alert(session: AsyncSession, alert_data: Dict[str, Any]):
    """Create a new alert."""
    try:
        alert = Alert(**alert_data)
        session.add(alert)
        await session.commit()
        await session.refresh(alert)
        return alert
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating alert: {str(e)}", exc_info=True)
        raise

async def update_alert(session: AsyncSession, alert_id: int, update_data: Dict[str, Any]):
    """Update an existing alert."""
    try:
        result = await session.execute(
            select(Alert).filter(Alert.id == alert_id)
        )
        alert = result.scalars().first()
        
        if not alert:
            return None
            
        for key, value in update_data.items():
            setattr(alert, key, value)
            
        alert.updated_at = datetime.utcnow()
        
        await session.commit()
        await session.refresh(alert)
        return alert
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating alert {alert_id}: {str(e)}", exc_info=True)
        raise

async def delete_alert(session: AsyncSession, alert_id: int):
    """Delete an alert."""
    try:
        result = await session.execute(
            select(Alert).filter(Alert.id == alert_id)
        )
        alert = result.scalars().first()
        
        if not alert:
            return False
            
        await session.delete(alert)
        await session.commit()
        return True
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error deleting alert {alert_id}: {str(e)}", exc_info=True)
        raise

# Device functions
async def create_device(session: AsyncSession, device_data: Dict[str, Any]) -> Device:
    """
    Create a new device.
    
    Args:
        session: Database session
        device_data: Dictionary containing device data
        
    Returns:
        The created Device object
    """
    try:
        device = Device(**device_data)
        session.add(device)
        await session.commit()
        await session.refresh(device)
        return device
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating device: {str(e)}", exc_info=True)
        raise

async def get_device_by_id(session: AsyncSession, device_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a device by its ID.
    
    Args:
        session: Database session
        device_id: ID of the device to retrieve
        
    Returns:
        Device dictionary if found, None otherwise
    """
    try:
        result = await session.execute(
            select(Device).where(Device.id == device_id)
        )
        device = result.scalars().first()
        
        if not device:
            return None
            
        return {
            'id': device.id,
            'name': device.name,
            'mac_address': device.mac_address,
            'ip_address': device.ip_address,
            'status': device.status,
            'created_at': device.created_at.isoformat(),
            'updated_at': device.updated_at.isoformat() if device.updated_at else None,
            'slice_id': device.slice_id
        }
    except Exception as e:
        logger.error(f"Error getting device {device_id}: {str(e)}", exc_info=True)
        raise

async def update_device(session: AsyncSession, device_id: int, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Update an existing device.
    
    Args:
        session: Database session
        device_id: ID of the device to update
        update_data: Dictionary containing fields to update
        
    Returns:
        Updated device dictionary if successful, None otherwise
    """
    try:
        result = await session.execute(
            select(Device).where(Device.id == device_id)
        )
        device = result.scalars().first()
        
        if not device:
            return None
            
        for key, value in update_data.items():
            setattr(device, key, value)
            
        device.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(device)
        
        return {
            'id': device.id,
            'name': device.name,
            'mac_address': device.mac_address,
            'ip_address': device.ip_address,
            'status': device.status,
            'created_at': device.created_at.isoformat(),
            'updated_at': device.updated_at.isoformat() if device.updated_at else None,
            'slice_id': device.slice_id
        }
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating device {device_id}: {str(e)}", exc_info=True)
        raise

async def delete_device(session: AsyncSession, device_id: int) -> bool:
    """
    Delete a device by its ID.
    
    Args:
        session: Database session
        device_id: ID of the device to delete
        
    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        result = await session.execute(
            select(Device).where(Device.id == device_id)
        )
        device = result.scalars().first()
        
        if not device:
            return False
            
        await session.delete(device)
        await session.commit()
        return True
    except Exception as e:
        await session.rollback()
        logger.error(f"Error deleting device {device_id}: {str(e)}", exc_info=True)
        raise

# Slice functions
async def create_slice(session: AsyncSession, slice_data: Dict[str, Any]) -> Slice:
    """
    Create a new network slice.
    
    Args:
        session: Database session
        slice_data: Dictionary containing slice data
        
    Returns:
        The created Slice object
    """
    try:
        slice_obj = Slice(**slice_data)
        session.add(slice_obj)
        await session.commit()
        await session.refresh(slice_obj)
        return slice_obj
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating slice: {str(e)}", exc_info=True)
        raise

async def get_slice_by_id(session: AsyncSession, slice_id: int) -> Optional[Slice]:
    """
    Get a slice by its ID.
    
    Args:
        session: Database session
        slice_id: ID of the slice to retrieve
        
    Returns:
        Slice object if found, None otherwise
    """
    try:
        result = await session.execute(
            select(Slice).where(Slice.id == slice_id)
        )
        return result.scalars().first()
    except Exception as e:
        logger.error(f"Error getting slice {slice_id}: {str(e)}", exc_info=True)
        raise

async def update_slice(session: AsyncSession, slice_id: int, update_data: Dict[str, Any]) -> Optional[Slice]:
    """
    Update an existing slice.
    
    Args:
        session: Database session
        slice_id: ID of the slice to update
        update_data: Dictionary containing fields to update
        
    Returns:
        Updated Slice object if successful, None otherwise
    """
    try:
        result = await session.execute(
            select(Slice).where(Slice.id == slice_id)
        )
        slice_obj = result.scalars().first()
        
        if not slice_obj:
            return None
            
        for key, value in update_data.items():
            setattr(slice_obj, key, value)
            
        await session.commit()
        await session.refresh(slice_obj)
        return slice_obj
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating slice {slice_id}: {str(e)}", exc_info=True)
        raise

async def delete_slice(session: AsyncSession, slice_id: int) -> bool:
    """
    Delete a slice by its ID.
    
    Args:
        session: Database session
        slice_id: ID of the slice to delete
        
    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        result = await session.execute(
            select(Slice).where(Slice.id == slice_id)
        )
        slice_obj = result.scalars().first()
        
        if not slice_obj:
            return False
            
        await session.delete(slice_obj)
        await session.commit()
        return True
    except Exception as e:
        await session.rollback()
        logger.error(f"Error deleting slice {slice_id}: {str(e)}", exc_info=True)
        raise

# Slice KPI functions
async def get_slice_kpis(session: AsyncSession, slice_id: int, limit: int = 100):
    """Get KPIs for a specific slice."""
    try:
        result = await session.execute(
            select(SliceKPI)
            .filter(SliceKPI.slice_id == slice_id)
            .order_by(SliceKPI.timestamp.desc())
            .limit(limit)
        )
        kpis = result.scalars().all()
        
        return [
            {
                'id': kpi.id,
                'slice_id': kpi.slice_id,
                'latency': float(kpi.latency) if kpi.latency else 0.0,
                'throughput': float(kpi.throughput) if kpi.throughput else 0.0,
                'packet_loss': float(kpi.packet_loss) if kpi.packet_loss else 0.0,
                'connected_devices': kpi.connected_devices or 0,
                'timestamp': kpi.timestamp.isoformat()
            }
            for kpi in kpis
        ]
        
    except Exception as e:
        logger.error(f"Error getting KPIs for slice {slice_id}: {str(e)}", exc_info=True)
        raise

async def get_kpi_by_id(session: AsyncSession, kpi_id: int):
    """Get a single KPI by ID."""
    try:
        result = await session.execute(
            select(SliceKPI).filter(SliceKPI.id == kpi_id)
        )
        kpi = result.scalars().first()
        
        if not kpi:
            return None
            
        return {
            'id': kpi.id,
            'slice_id': kpi.slice_id,
            'latency': float(kpi.latency) if kpi.latency else 0.0,
            'throughput': float(kpi.throughput) if kpi.throughput else 0.0,
            'packet_loss': float(kpi.packet_loss) if kpi.packet_loss else 0.0,
            'connected_devices': kpi.connected_devices or 0,
            'timestamp': kpi.timestamp.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting KPI {kpi_id}: {str(e)}", exc_info=True)
        raise

async def create_kpi(session: AsyncSession, kpi_data: Dict[str, Any]):
    """Create a new KPI record."""
    try:
        kpi = SliceKPI(**kpi_data)
        session.add(kpi)
        await session.commit()
        await session.refresh(kpi)
        return kpi
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating KPI: {str(e)}", exc_info=True)
        raise

async def update_kpi(session: AsyncSession, kpi_id: int, update_data: Dict[str, Any]):
    """Update an existing KPI."""
    try:
        result = await session.execute(
            select(SliceKPI).filter(SliceKPI.id == kpi_id)
        )
        kpi = result.scalars().first()
        
        if not kpi:
            return None
            
        for key, value in update_data.items():
            setattr(kpi, key, value)
            
        await session.commit()
        await session.refresh(kpi)
        return kpi
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating KPI {kpi_id}: {str(e)}", exc_info=True)
        raise

async def delete_kpi(session: AsyncSession, kpi_id: int):
    """Delete a KPI record."""
    try:
        result = await session.execute(
            select(SliceKPI).filter(SliceKPI.id == kpi_id)
        )
        kpi = result.scalars().first()
        
        if not kpi:
            return False
            
        await session.delete(kpi)
        await session.commit()
        return True
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error deleting KPI {kpi_id}: {str(e)}", exc_info=True)
        raise

# Metric functions
async def get_device_metrics(session: AsyncSession, device_id: int, time_range: str = '1h'):
    """
    Get metrics for a specific device.
    
    Args:
        session: Database session
        device_id: ID of the device
        time_range: Time range for metrics ('1h', '24h', '7d', '30d')
        
    Returns:
        List of metric dictionaries for the device
    """
    try:
        # Calculate time range
        now = datetime.utcnow()
        if time_range == '1h':
            start_time = now - timedelta(hours=1)
        elif time_range == '24h':
            start_time = now - timedelta(days=1)
        elif time_range == '7d':
            start_time = now - timedelta(days=7)
        elif time_range == '30d':
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(hours=1)  # Default to 1 hour
            
        # Query metrics for the device
        result = await session.execute(
            select(Metric)
            .where(and_(
                Metric.device_id == device_id,
                Metric.timestamp >= start_time
            ))
            .order_by(Metric.timestamp.desc())
        )
        
        metrics = result.scalars().all()
        return [
            {
                'id': m.id,
                'timestamp': m.timestamp.isoformat(),
                'throughput': m.throughput,
                'latency': m.latency,
                'packet_loss': m.packet_loss,
                'jitter': m.jitter,
                'device_id': m.device_id,
                'slice_id': m.slice_id
            }
            for m in metrics
        ]
    except Exception as e:
        logger.error(f"Error getting device metrics: {str(e)}", exc_info=True)
        return []

async def get_metric_by_id(session: AsyncSession, metric_id: int):
    """Get a single metric by ID."""
    try:
        result = await session.execute(
            select(Metric).filter(Metric.id == metric_id)
        )
        metric = result.scalars().first()
        
        if not metric:
            return None
            
        return {
            'id': metric.id,
            'name': metric.name,
            'value': float(metric.value) if metric.value else 0.0,
            'unit': metric.unit,
            'timestamp': metric.timestamp.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting metric {metric_id}: {str(e)}", exc_info=True)
        raise

async def create_metric(session: AsyncSession, metric_data: Dict[str, Any]):
    """Create a new metric."""
    try:
        metric = Metric(**metric_data)
        session.add(metric)
        await session.commit()
        await session.refresh(metric)
        return metric
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating metric: {str(e)}", exc_info=True)
        raise

async def update_metric(session: AsyncSession, metric_id: int, update_data: Dict[str, Any]):
    """Update an existing metric."""
    try:
        result = await session.execute(
            select(Metric).filter(Metric.id == metric_id)
        )
        metric = result.scalars().first()
        
        if not metric:
            return None
            
        for key, value in update_data.items():
            setattr(metric, key, value)
            
        await session.commit()
        await session.refresh(metric)
        return metric
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating metric {metric_id}: {str(e)}", exc_info=True)
        raise

async def delete_metric(session: AsyncSession, metric_id: int):
    """Delete a metric."""
    try:
        result = await session.execute(
            select(Metric).filter(Metric.id == metric_id)
        )
        metric = result.scalars().first()
        
        if not metric:
            return False
            
        await session.delete(metric)
        await session.commit()
        return True
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error deleting metric {metric_id}: {str(e)}", exc_info=True)
        raise
