"""
Database queries and utilities for the dashboard.
"""
import random
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.expression import case

from app.db.models import Slice, SliceKPI, Alert, Metric

async def get_all_slices(session: AsyncSession) -> List[Dict[str, Any]]:
    """Retrieve all slices with their latest KPIs."""
    try:
        # Get the latest KPI for each slice
        subq = (
            select(
                SliceKPI.slice_id,
                func.max(SliceKPI.timestamp).label('max_timestamp')
            )
            .group_by(SliceKPI.slice_id)
            .subquery()
        )
        
        stmt = (
            select(
                Slice.id,
                Slice.name,
                Slice.status,
                Slice.updated_at,
                Slice.max_devices,
                SliceKPI.connected_devices,
                SliceKPI.latency,
                SliceKPI.throughput,
                SliceKPI.timestamp
            )
            .select_from(Slice)
            .outerjoin(
                subq,
                Slice.id == subq.c.slice_id
            )
            .outerjoin(
                SliceKPI,
                and_(
                    SliceKPI.slice_id == subq.c.slice_id,
                    SliceKPI.timestamp == subq.c.max_timestamp
                )
            )
        )
        
        print("Executing query:", stmt)  # Log the query
        result = await session.execute(stmt)
        rows = result.all()
        print(f"Retrieved {len(rows)} rows")  # Log number of rows
        
        slices = []
        for row in rows:
            try:
                max_devices = row[4] or 0
                connected_devices = row[5] or 0
                capacity_pct = (connected_devices / max_devices * 100) if max_devices > 0 else 0
                
                slice_data = {
                    'id': row[0],  # Slice.id
                    'name': row[1],  # Slice.name
                    'status': row[2],  # Slice.status
                    'users': connected_devices,  # Connected devices count
                    'capacity': f"{capacity_pct:.1f}%",  # Capacity percentage
                    'latency': f"{row[6]:.2f} ms" if row[6] is not None else 'N/A',  # SliceKPI.latency
                    'throughput': f"{row[7]:.1f} Mbps" if row[7] is not None else 'N/A',  # SliceKPI.throughput
                    'last_updated': (row[8] if row[8] is not None else row[3]).strftime('%Y-%m-%d %H:%M:%S')  # timestamp or updated_at
                }
                slices.append(slice_data)
            except Exception as row_error:
                print(f"Error processing row {row}: {str(row_error)}")
                continue
        
        print(f"Successfully processed {len(slices)} slices")
        return slices
        
    except Exception as e:
        print(f"Error in get_all_slices: {str(e)}")
        import traceback
        traceback.print_exc()
        return []  # Return empty list on error to prevent dashboard from breaking

async def get_kpi_summary(session: AsyncSession) -> Dict[str, Any]:
    """Get summary KPIs for the dashboard."""
    try:
        # Get latest KPIs for all slices
        subq = (
            select(
                SliceKPI.slice_id,
                func.max(SliceKPI.timestamp).label('max_timestamp')
            )
            .group_by(SliceKPI.slice_id)
            .subquery()
        )
        
        # Get the latest KPIs for each slice
        latest_kpis = (
            select(
                SliceKPI.slice_id,
                SliceKPI.connected_devices,
                SliceKPI.latency,
                SliceKPI.throughput,
                SliceKPI.timestamp
            )
            .select_from(SliceKPI)
            .join(
                subq,
                and_(
                    SliceKPI.slice_id == subq.c.slice_id,
                    SliceKPI.timestamp == subq.c.max_timestamp
                )
            )
        )
        
        print("Executing KPI summary query:", latest_kpis)  # Log the query
        result = await session.execute(latest_kpis)
        kpi_rows = result.all()
        
        # Calculate summary metrics
        total_devices = 0
        total_latency = 0.0
        total_throughput = 0.0
        active_slices = 0
        
        for row in kpi_rows:
            if row[1] is not None:  # connected_devices
                total_devices += row[1]
            if row[2] is not None:  # latency
                total_latency += row[2]
            if row[3] is not None:  # throughput
                total_throughput += row[3]
            active_slices += 1
        
        # Calculate averages
        avg_latency = total_latency / active_slices if active_slices > 0 else 0
        avg_throughput = total_throughput / active_slices if active_slices > 0 else 0
        
        # Get total slices count
        total_slices_result = await session.execute(select(func.count(Slice.id)))
        total_slices = total_slices_result.scalar() or 0
        
        # Get active alerts count
        active_alerts_result = await session.execute(
            select(func.count(Alert.id)).where(Alert.resolved == False)
        )
        active_alerts = active_alerts_result.scalar() or 0
        
        return {
            'total_slices': total_slices,
            'active_slices': active_slices,
            'total_devices': total_devices,
            'avg_latency': f"{avg_latency:.2f} ms",
            'avg_throughput': f"{avg_throughput:.2f} Mbps",
            'active_alerts': active_alerts,
            'last_updated': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        print(f"Error in get_kpi_summary: {str(e)}")
        import traceback
        traceback.print_exc()
        # Return default values in case of error
        return {
            'total_slices': 0,
            'active_slices': 0,
            'total_devices': 0,
            'avg_latency': 'N/A',
            'avg_throughput': 'N/A',
            'active_alerts': 0,
            'last_updated': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }

async def get_recent_activity(session: AsyncSession, limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent activity for the dashboard."""
    try:
        stmt = (
            select(
                Alert.timestamp,
                Alert.level,
                Alert.message,
                Alert.entity_type,
                Alert.entity_id,
                Alert.resolved,
                Alert.context
            )
            .order_by(Alert.timestamp.desc())
            .limit(limit)
        )
        
        print("Executing recent activity query:", stmt)  # Log the query
        result = await session.execute(stmt)
        rows = result.all()
        
        activities = []
        for row in rows:
            try:
                activity = {
                    'timestamp': row[0].strftime('%Y-%m-%d %H:%M:%S'),
                    'level': row[1],
                    'message': row[2],
                    'entity_type': row[3],
                    'entity_id': row[4],
                    'resolved': row[5],
                    'context': row[6] or {}
                }
                activities.append(activity)
            except Exception as row_error:
                print(f"Error processing activity row {row}: {str(row_error)}")
                continue
        
        print(f"Retrieved {len(activities)} recent activities")
        return activities
        
    except Exception as e:
        print(f"Error in get_recent_activity: {str(e)}")
        import traceback
        traceback.print_exc()
        return []  # Return empty list on error to prevent dashboard from breaking

async def get_throughput_latency_data(session: AsyncSession, slice_id: str = None, hours: int = 24) -> Tuple[List[str], List[float], List[float]]:
    """Get throughput and latency data for charts.
    
    Args:
        session: Database session
        slice_id: Optional slice ID to filter by
        hours: Number of hours of data to retrieve
        
    Returns:
        Tuple of (timestamps, throughput_values, latency_values)
    """
    try:
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        print(f"Fetching throughput/latency data from {start_time} to {end_time}" + 
              (f" for slice {slice_id}" if slice_id else " for all slices"))
        
        # Build base query
        stmt = (
            select(
                func.to_char(SliceKPI.timestamp, 'HH24:MI').label('time'),
                func.coalesce(func.avg(SliceKPI.throughput), 0).label('avg_throughput'),
                func.coalesce(func.avg(SliceKPI.latency), 0).label('avg_latency')
            )
            .where(SliceKPI.timestamp.between(start_time, end_time))
            .group_by('time')
            .order_by('time')
        )
        
        if slice_id:
            stmt = stmt.where(SliceKPI.slice_id == slice_id)
        
        print("Executing query:", stmt)  # Log the query
        result = await session.execute(stmt)
        rows = result.all()
        
        # Process data with error handling
        timestamps = []
        throughput_values = []
        latency_values = []
        
        for row in rows:
            try:
                timestamps.append(str(row[0]))
                throughput_values.append(float(row[1] or 0))
                latency_values.append(float(row[2] or 0))
            except Exception as e:
                print(f"Error processing row {row}: {str(e)}")
                continue
        
        print(f"Retrieved {len(timestamps)} data points")
        return timestamps, throughput_values, latency_values
        
    except Exception as e:
        print(f"Error in get_throughput_latency_data: {str(e)}")
        return [], [], []
    finally:
        # Cleanup code can go here if needed
        pass
    
async def get_metrics_data(
    session: AsyncSession,
    start_time: datetime,
    end_time: datetime,
    slice_id: str = None
) -> Dict[str, Any]:
    """
    Get metrics data for the specified time range and optional slice.
    
    Args:
        session: Database session
        start_time: Start time for metrics
        end_time: End time for metrics
        slice_id: Optional slice ID to filter by
        
    Returns:
        Dictionary containing metrics data including throughput and latency
    """
    try:
        # Get current time in UTC
        now = datetime.now(timezone.utc)
        
        # Base query
        query = select(
            Metric.timestamp,
            Metric.metric_type,
            func.avg(Metric.value).label('value')
        ).where(
            and_(
                Metric.timestamp >= start_time,
                Metric.timestamp <= end_time
            )
        )
        
        # Add slice filter if provided
        if slice_id:
            query = query.where(Metric.slice_id == slice_id)
            
        # Group by time window and metric type
        query = query.group_by(
            func.date_trunc('minute', Metric.timestamp),
            Metric.metric_type
        ).order_by(
            Metric.timestamp.asc()
        )
        
        # Execute query
        result = await session.execute(query)
        rows = result.all()
        
        # Process results
        metrics = {
            'throughput': [],
            'latency': [],
            'timestamps': [],
            'last_updated': now.isoformat()
        }
        
        # Track unique timestamps
        seen_timestamps = set()
        
        for row in rows:
            timestamp = row.timestamp.isoformat()
            if timestamp not in seen_timestamps:
                metrics['timestamps'].append(timestamp)
                seen_timestamps.add(timestamp)
                
            if row.metric_type == 'throughput':
                metrics['throughput'].append({
                    'x': timestamp,
                    'y': float(row.value)
                })
            elif row.metric_type == 'latency':
                metrics['latency'].append({
                    'x': timestamp,
                    'y': float(row.value)
                })
        
        # Add slice info if available
        if slice_id:
            slice_query = select(Slice).where(Slice.id == slice_id)
            slice_result = await session.execute(slice_query)
            slice_data = slice_result.scalar_one_or_none()
            
            if slice_data:
                metrics['slice'] = {
                    'id': slice_data.id,
                    'name': slice_data.name,
                    'status': slice_data.status
                }
        
        # Add summary stats
        if metrics['throughput']:
            throughput_values = [m['y'] for m in metrics['throughput']]
            metrics['throughput_stats'] = {
                'min': min(throughput_values) if throughput_values else 0,
                'max': max(throughput_values) if throughput_values else 0,
                'avg': sum(throughput_values) / len(throughput_values) if throughput_values else 0
            }
            
        if metrics['latency']:
            latency_values = [m['y'] for m in metrics['latency']]
            metrics['latency_stats'] = {
                'min': min(latency_values) if latency_values else 0,
                'max': max(latency_values) if latency_values else 0,
                'avg': sum(latency_values) / len(latency_values) if latency_values else 0
            }
        
        return metrics
        
    except Exception as e:
        # Log the error and return empty metrics
        print(f"Error in get_metrics_data: {str(e)}")
        return {
            'throughput': [],
            'latency': [],
            'timestamps': [],
            'last_updated': datetime.now(timezone.utc).isoformat(),
            'error': str(e)
        }
        
    except Exception as e:
        print(f"Error in get_throughput_latency_data: {str(e)}")
        import traceback
        traceback.print_exc()
        # Return empty lists on error to prevent chart rendering issues
        return [], [], []
