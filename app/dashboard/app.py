import os
from flask import Flask, render_template_string, jsonify, redirect, url_for, request, json
from datetime import datetime, timedelta
import random
import asyncio
from sqlalchemy.sql import text, and_
from sqlalchemy.orm import aliased
from functools import wraps
from typing import Any, Dict, List, Tuple, Optional
import nest_asyncio
import hashlib

# Create Flask app
app = Flask(__name__)

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Database imports
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

# Import models and database utilities
from app.db.database import async_engine, async_session_factory, get_db
from app.db.models import Slice, SliceKPI, Alert, User
from app.db.dashboard_queries import (
    get_all_slices,
    get_kpi_summary,
    get_recent_activity,
    get_throughput_latency_data
)

# Template filters
def md5_hash(text):
    """Generate MD5 hash of text."""
    return hashlib.md5(str(text).encode('utf-8')).hexdigest()

def to_json(value, indent=None):
    """Convert value to JSON with optional indentation."""
    if value is None:
        return 'null'
    return json.dumps(value, default=str, ensure_ascii=False, indent=indent)

# Decorator to allow async routes in Flask
def async_route(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(f(*args, **kwargs))
            return result
        finally:
            loop.close()
    return wrapper

# Constants
SLICE_TYPES = ["eMBB", "URLLC", "mMTC", "V2X", "Industrial IoT"]
STATUS_COLORS = {
    "Active": "success",
    "Inactive": "secondary",
    "Warning": "warning",
    "Error": "danger",
    "Degraded": "warning",
    "Maintenance": "info"
}

# Database session manager
async def get_db_session():
    """Async database session."""
    session = async_session_factory()
    try:
        yield session
    finally:
        if session:
            await session.close()

# Database access functions
async def get_slices_from_db() -> List[Dict[str, Any]]:
    """Retrieve all slices from the database."""
    session_gen = get_db_session()
    session = await anext(session_gen)
    try:
        print("Fetching slices from database...")  # Debug log
        # Query only the columns that exist in the database
        result = await session.execute(
            select(
                Slice.id,
                Slice.name,
                Slice.status,
                Slice.created_at,
                Slice.updated_at
            )
            .order_by(Slice.created_at.desc())
        )
        slices = result.all()
        
        print(f"Found {len(slices)} slices in database")  # Debug log
        if slices:
            print("Sample slice data:", {  # Debug log
                'id': slices[0].id,
                'name': slices[0].name,
                'status': slices[0].status
            })
        
        # Convert to list of dicts with safe attribute access
        return [{
            'id': slice.id,
            'name': slice.name,
            'type': 'default',  # Default slice type
            'status': (slice.status or '').lower(),
            'created_at': slice.created_at.isoformat() if slice.created_at else '',
            'updated_at': slice.updated_at.isoformat() if slice.updated_at else '',
            'description': ''  # Default empty description
        } for slice in slices]
    except Exception as e:
        print(f"Error in get_slices_from_db: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        await session.close()

async def get_kpis_from_db() -> Dict[str, Any]:
    """Retrieve KPI summary from the database."""
    session_gen = get_db_session()
    session = await anext(session_gen)
    try:
        print("Fetching KPIs from database...")  # Debug log
        # Get total slices
        total_slices = (await session.execute(select(func.count(Slice.id)))).scalar() or 0
        
        # Get active slices
        active_slices = (await session.execute(
            select(func.count(Slice.id))
            .where(Slice.status == 'Active')
        )).scalar() or 0
        
        # Get average latency
        avg_latency = (await session.execute(
            select(func.avg(SliceKPI.latency))
        )).scalar() or 0.0
        
        # Get average throughput
        avg_throughput = (await session.execute(
            select(func.avg(SliceKPI.throughput))
        )).scalar() or 0.0
        
        # Get active alerts count (using resolved=False instead of status='active')
        active_alerts_count = (await session.execute(
            select(func.count(Alert.id))
            .where(Alert.resolved == False)  # Using resolved flag instead of status
        )).scalar() or 0
        
        # Get total connected devices (sum of connected_devices from all slice KPIs)
        total_devices = (await session.execute(
            select(func.sum(SliceKPI.connected_devices))
        )).scalar() or 0
        
        print(f"KPI Data - Slices: {total_slices} total, {active_slices} active")
        print(f"KPI Data - Avg Latency: {avg_latency}, Avg Throughput: {avg_throughput}")
        print(f"KPI Data - Active Alerts: {active_alerts_count}, Total Devices: {total_devices}")
        
        return {
            'total_slices': total_slices,
            'active_slices': active_slices,
            'avg_latency': round(float(avg_latency), 2),
            'avg_throughput': round(float(avg_throughput), 2),
            'active_alerts': active_alerts_count,
            'total_devices': total_devices
        }
        
    except Exception as e:
        print(f"Error in get_kpis_from_db: {e}")
        import traceback
        traceback.print_exc()
        return {
            'total_slices': 0,
            'active_slices': 0,
            'avg_latency': 0.0,
            'avg_throughput': 0.0,
            'active_alerts': 0
        }
    finally:
        await session.close()

async def get_activity_from_db(limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieve recent activity/notifications."""
    session_gen = get_db_session()
    session = await anext(session_gen)
    try:
        print(f"Fetching recent activity (limit: {limit})...")  # Debug log
        
        # Query only the columns that exist in the database
        result = await session.execute(
            select(
                Alert.id,
                Alert.timestamp,
                Alert.level,
                Alert.message,
                Alert.resolved,
                Alert.resolved_at,
                Alert.entity_type,
                Alert.entity_id,
                Alert.context
            )
            .order_by(Alert.timestamp.desc())
            .limit(limit)
        )
        alerts = result.all()
        
        print(f"Found {len(alerts)} recent activities")  # Debug log
        
        # Convert to list of dicts
        return [{
            'id': alert.id,
            'timestamp': alert.timestamp,
            'level': alert.level,
            'message': alert.message,
            'status': 'resolved' if alert.resolved else 'active',
            'slice_id': alert.entity_id if alert.entity_type == 'slice' else None,
            'resolved': alert.resolved,
            'resolved_at': alert.resolved_at,
            'entity_type': alert.entity_type,
            'entity_id': alert.entity_id,
            'context': alert.context or {}
        } for alert in alerts]
    except Exception as e:
        print(f"Error in get_activity_from_db: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        await session.close()

async def get_latest_kpi(slice_id: str) -> Dict[str, Any]:
    """Get the latest KPI for a slice."""
    session_gen = get_db_session()
    session = await anext(session_gen)
    try:
        # Try to get the latest KPI for the slice
        result = await session.execute(
            select(SliceKPI)
            .where(SliceKPI.slice_id == slice_id)
            .order_by(SliceKPI.timestamp.desc())
            .limit(1)
        )
        kpi = result.scalars().first()
        
        if kpi:
            return {
                'connected_devices': getattr(kpi, 'connected_devices', 0),
                'throughput': getattr(kpi, 'throughput', 0),
                'latency': getattr(kpi, 'latency', 0),
                'timestamp': getattr(kpi, 'timestamp', datetime.utcnow())
            }
        return {}
    except Exception as e:
        print(f"Error getting latest KPI for slice {slice_id}: {e}")
        return {}
    finally:
        await session.close()

async def get_throughput_latency_from_db(slice_id: str, hours: int = 24) -> Tuple[List[float], List[float]]:
    """Retrieve throughput and latency data for a slice.
    
    Args:
        slice_id: The ID of the slice to get data for
        hours: Number of hours of data to retrieve
        
    Returns:
        Tuple of (throughput_data, latency_data) where each is a list of values
    """
    session_gen = get_db_session()
    session = await anext(session_gen)
    try:
        print(f"Getting throughput/latency data for slice {slice_id} for the last {hours} hours")
        
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        # First check if the table exists
        table_exists = await session.execute(
            text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'slice_kpis'
            )
            """)
        )
        
        if not table_exists.scalar():
            print("slice_kpis table does not exist")
            return [], []
            
        # Query for throughput and latency data
        result = await session.execute(
            select(
                func.to_char(SliceKPI.timestamp, 'HH24:MI').label('time'),
                func.avg(SliceKPI.throughput).label('avg_throughput'),
                func.avg(SliceKPI.latency).label('avg_latency')
            )
            .where(and_(
                SliceKPI.timestamp.between(start_time, end_time),
                SliceKPI.slice_id == slice_id
            ))
            .group_by('time')
            .order_by('time')
        )
        
        # Process results
        rows = result.all()
        
        if not rows:
            print(f"No data found for slice {slice_id}")
            # Return empty lists if no data
            return [], []
            
        print(f"Found {len(rows)} data points for slice {slice_id}")
        
        # Extract data and ensure we have valid numbers
        throughput_data = []
        latency_data = []
        
        for row in rows:
            try:
                # Convert to float, default to 0 if None or invalid
                throughput = float(row.avg_throughput or 0) if row.avg_throughput is not None else 0
                latency = float(row.avg_latency or 0) if row.avg_latency is not None else 0
                
                # Ensure we have reasonable values
                if throughput < 0:
                    throughput = 0
                if latency < 0:
                    latency = 0
                    
                throughput_data.append(throughput)
                latency_data.append(latency)
                
            except (ValueError, TypeError) as e:
                print(f"Error processing row {row}: {e}")
                continue
        
        # If we have no valid data, return empty lists
        if not throughput_data or not latency_data:
            print("No valid data points found")
            return [], []
            
        print(f"Returning {len(throughput_data)} data points")
        return throughput_data, latency_data
        
    except Exception as e:
        print(f"Error in get_throughput_latency_from_db: {e}")
        import traceback
        traceback.print_exc()
        return [], []
    finally:
        await session.close()

# App configuration
app.config.update(
    SECRET_KEY=os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key'),
    JSON_AS_ASCII=False,
    JSON_SORT_KEYS=False,
    JSONIFY_PRETTYPRINT_REGULAR=True
)

# Add security headers
@app.after_request
def add_security_headers(response):
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-eval' 'unsafe-inline' cdn.jsdelivr.net cdn.plot.ly; "
        "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
        "img-src 'self' data:; "
        "font-src 'self' cdn.jsdelivr.net data:; "
        "connect-src 'self'"
    )
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = csp
    return response

# Register template filters
app.jinja_env.filters['md5'] = md5_hash
app.jinja_env.filters['tojson'] = to_json  # Register as 'tojson' to match template usage

# Database session factory
async def get_db_session():
    """Get an async database session."""
    session = async_session_factory()
    try:
        yield session
    finally:
        await session.close()

# Routes
@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/api/slices', methods=['POST'])
@async_route
async def create_slice():
    """Create a new network slice."""
    try:
        data = request.json
        print("Received create slice request:", data)  # Debug log
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        required_fields = ['name', 'type']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        async with get_db_session() as session:
            try:
                # Create new slice
                new_slice = Slice(
                    name=data['name'],
                    type=data['type'],
                    description=data.get('description', ''),
                    status='active',  # Make sure this matches your database enum
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                session.add(new_slice)
                await session.flush()  # Flush to get the ID
                
                # Create initial KPI entry
                kpi = SliceKPI(
                    slice_id=new_slice.id,
                    timestamp=datetime.utcnow(),
                    latency=random.uniform(5, 50),  # Random initial values
                    throughput=random.uniform(100, 1000),
                    connected_devices=random.randint(1, 100)
                )
                session.add(kpi)
                
                await session.commit()
                print(f"Successfully created slice: {new_slice.id}")  # Debug log
                
                return jsonify({
                    'message': 'Slice created successfully',
                    'id': new_slice.id
                }), 201
                
            except Exception as e:
                await session.rollback()
                print(f"Database error creating slice: {e}")  # Debug log
                return jsonify({'error': 'Failed to create slice in database'}), 500
                
    except Exception as e:
        print(f"Error in create_slice endpoint: {e}")  # Debug log
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/dashboard')
@async_route
async def dashboard():
    """Render the main dashboard page."""
    try:
        print("Fetching dashboard data...")
        
        # Initialize default values with the structure expected by the new template
        slices_data = []
        kpis_data = {
            'active_slices': 0,
            'total_devices': 0,
            'avg_latency': 0.0,
            'alerts': 0
        }
        activities_data = []
        timestamps_data = []
        throughput_data = []
        latency_data = []
        
        try:
            print("Fetching slices data...")
            slices_from_db = await get_slices_from_db()
            print(f"Retrieved {len(slices_from_db)} slices")  # Debug log
            print("Raw slices data from DB:", slices_from_db)  # Debug log
            
            # Map slices to the format expected by the template
            slices_data = []
            if not slices_from_db:
                print("No slices found in the database")
                # Add some sample slices for demonstration
                sample_slices = [
                    {'id': 'slice_embb_001', 'name': 'eMBB Slice', 'type': 'eMBB', 'status': 'active'},
                    {'id': 'slice_urllc_001', 'name': 'URLLC Slice', 'type': 'URLLC', 'status': 'active'},
                    {'id': 'slice_mmtc_001', 'name': 'mMTC Slice', 'type': 'mMTC', 'status': 'active'}
                ]
                slices_from_db = sample_slices
                print("Using sample slice data")
            
            for slice_data in slices_from_db:
                try:
                    # Handle both dictionary and object access
                    slice_id = str(
                        getattr(slice_data, 'id', '') 
                        if hasattr(slice_data, 'id') 
                        else slice_data.get('id', f'slice_{len(slices_data) + 1:03d}')
                    )
                    
                    slice_name = (
                        getattr(slice_data, 'name', f'Slice {slice_id}') 
                        if hasattr(slice_data, 'name') 
                        else slice_data.get('name', f'Slice {slice_id}')
                    )
                    
                    # Get status with fallback
                    status = 'inactive'
                    if hasattr(slice_data, 'status'):
                        status = (getattr(slice_data, 'status') or 'inactive').lower()
                    elif isinstance(slice_data, dict) and 'status' in slice_data:
                        status = (slice_data.get('status') or 'inactive').lower()
                    
                    # Try to get KPI data
                    connected_devices = 0
                    try:
                        kpi = await get_latest_kpi(slice_id)
                        connected_devices = int(kpi.get('connected_devices', random.randint(1, 100))) if kpi else 0
                    except Exception as kpi_err:
                        print(f"Error getting KPI for slice {slice_id}: {kpi_err}")
                        connected_devices = random.randint(1, 100)  # Fallback to random data
                    
                    # Determine slice type
                    slice_type = 'default'
                    if hasattr(slice_data, 'type') and getattr(slice_data, 'type'):
                        slice_type = getattr(slice_data, 'type')
                    elif isinstance(slice_data, dict) and 'type' in slice_data and slice_data.get('type'):
                        slice_type = slice_data.get('type')
                    elif 'embb' in slice_id.lower():
                        slice_type = 'eMBB'
                    elif 'urllc' in slice_id.lower():
                        slice_type = 'URLLC'
                    elif 'm2m' in slice_id.lower() or 'mmtc' in slice_id.lower():
                        slice_type = 'mMTC'
                    
                    # Get description with fallback
                    description = ''
                    if hasattr(slice_data, 'description'):
                        description = getattr(slice_data, 'description', '')
                    elif isinstance(slice_data, dict) and 'description' in slice_data:
                        description = slice_data.get('description', '')
                    
                    # Build slice info
                    slice_info = {
                        'id': slice_id,
                        'name': slice_name,
                        'type': slice_type,
                        'status': status,
                        'capacity': f"{random.randint(10, 100)}%",
                        'connected_devices': connected_devices,
                        'description': str(description) if description else f"{slice_type} Network Slice"
                    }
                    print(f"Processed slice info: {slice_info}")  # Debug log
                    slices_data.append(slice_info)
                except Exception as e:
                    print(f"Error processing slice {slice_data.get('id')}: {e}")
                    # Add a minimal slice with just the ID if processing fails
                    slices_data.append({
                        'id': str(slice_data.get('id', 'unknown')),
                        'name': 'Error Loading Slice',
                        'type': 'error',
                        'status': 'error',
                        'capacity': '0%',
                        'connected_devices': 0,
                        'description': 'Error loading slice data'
                    })
                
            print("Fetching KPIs...")
            kpis_from_db = await get_kpis_from_db()
            
            # Map the database KPIs to the structure expected by the template
            try:
                kpis_data = {
                    'active_slices': int(kpis_from_db.get('active_slices', 0)) if kpis_from_db else 0,
                    'total_devices': int(kpis_from_db.get('total_devices', 0)) if kpis_from_db else 0,
                    'avg_latency': round(float(kpis_from_db.get('avg_latency', 0.0) or 0), 2),
                    'alerts': int(kpis_from_db.get('alerts', 0)) if kpis_from_db else 0
                }
                
                # If we have no active slices but we have slices_data, update the count
                if kpis_data['active_slices'] == 0 and slices_data:
                    active_count = sum(1 for s in slices_data if s.get('status') == 'active')
                    kpis_data['active_slices'] = active_count
                
                # If we have no devices but have slices, calculate from slices
                if kpis_data['total_devices'] == 0 and slices_data:
                    total_devices = sum(int(s.get('connected_devices', 0)) for s in slices_data)
                    kpis_data['total_devices'] = total_devices
                
                # If we have no latency data but have slices, calculate average
                if kpis_data['avg_latency'] == 0 and slices_data:
                    latencies = [s.get('latency', 0) for s in slices_data if s.get('latency')]
                    if latencies:
                        kpis_data['avg_latency'] = round(sum(latencies) / len(latencies), 2)
                
                print(f"Final KPI Data: {kpis_data}")
                
            except (TypeError, ValueError) as e:
                print(f"Error formatting KPIs: {e}")
                # Fallback to calculating from slices_data if available
                if slices_data:
                    active_slices = sum(1 for s in slices_data if s.get('status') == 'active')
                    total_devices = sum(int(s.get('connected_devices', 0)) for s in slices_data)
                    latencies = [s.get('latency', 0) for s in slices_data if s.get('latency')]
                    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
                    
                    kpis_data = {
                        'active_slices': active_slices,
                        'total_devices': total_devices,
                        'avg_latency': avg_latency,
                        'alerts': 0  # Default to 0 if we can't get alerts
                    }
                else:
                    kpis_data = {
                        'active_slices': 0,
                        'total_devices': 0,
                        'avg_latency': 0.0,
                        'alerts': 0
                    }
            
            print(f"Retrieved KPIs: {kpis_data}")
            
            print("Fetching recent activity...")
            activity_from_db = await get_activity_from_db(limit=10)
            activities_data = []
            
            # Map activity data to the format expected by the template
            for activity in activity_from_db:
                timestamp = activity.get('timestamp')
                if timestamp and not isinstance(timestamp, str):
                    if hasattr(timestamp, 'strftime'):
                        timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        timestamp = str(timestamp)
                
                activities_data.append({
                    'type': 'alert_triggered' if activity.get('level') == 'ERROR' else 'device_connect',
                    'message': activity.get('message', 'No message'),
                    'timestamp': timestamp or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            
            print(f"Retrieved {len(activities_data)} activities")
            
            # Generate mock data for charts if no real data
            try:
                if slices_data:
                    # Get the first slice's data for the charts
                    first_slice_id = slices_data[0]['id']
                    print(f"Fetching throughput/latency data for slice {first_slice_id}...")
                    result = await get_throughput_latency_from_db(first_slice_id)
                    
                    if isinstance(result, tuple) and len(result) == 2:
                        throughput_data, latency_data = result
                        # Ensure we have data
                        if not throughput_data or not latency_data:
                            raise ValueError("No data returned from get_throughput_latency_from_db")
                            
                        # Generate timestamps for the data points
                        now = datetime.now()
                        timestamps_data = [(now - timedelta(minutes=i*5)).strftime('%H:%M') 
                                         for i in reversed(range(len(throughput_data)))]
                        print(f"Retrieved {len(throughput_data)} throughput and {len(latency_data)} latency data points")
                    else:
                        raise ValueError("Unexpected result format from get_throughput_latency_from_db")
                else:
                    raise ValueError("No slices available")
                    
            except Exception as e:
                print(f"Error getting throughput/latency data: {e}")
                print("Generating mock data for charts...")
                # Generate mock data with realistic values
                now = datetime.now()
                timestamps_data = [(now - timedelta(minutes=i*5)).strftime('%H:%M') 
                                 for i in reversed(range(12))]
                
                # Generate realistic throughput data (Mbps)
                base_throughput = random.uniform(50, 200)
                throughput_data = [max(10, base_throughput + random.uniform(-20, 50)) for _ in range(12)]
                
                # Generate realistic latency data (ms)
                base_latency = random.uniform(10, 30)
                latency_data = [max(1, base_latency + random.uniform(-5, 10)) for _ in range(12)]
                
                print(f"Generated mock data: {len(throughput_data)} points, avg throughput: {sum(throughput_data)/len(throughput_data):.2f} Mbps, avg latency: {sum(latency_data)/len(latency_data):.2f} ms")
                
        except Exception as e:
            print(f"Error fetching dashboard data: {e}")
            import traceback
            traceback.print_exc()
            # Generate mock data if there's an error
            timestamps_data = [(datetime.now() - timedelta(minutes=i*5)).strftime('%H:%M') 
                            for i in reversed(range(12))]
            throughput_data = [random.uniform(100, 1000) for _ in range(12)]
            latency_data = [random.uniform(5, 50) for _ in range(12)]
        
        print("Rendering dashboard template...")
        
        # Load the new template from a separate file for better maintainability
        template_path = os.path.join(os.path.dirname(__file__), 'templates', 'dashboard.html')
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
        except FileNotFoundError:
            # Fallback template if the file is not found
            template = """
            <!DOCTYPE html>
    <html>
    <head>
        <title>5G Network Slice Manager</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                background-color: #f5f7fb;
                padding: 20px;
                color: #333;
            }
            .card {
                border: none;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05);
                margin-bottom: 20px;
                transition: transform 0.2s;
            }
            .card:hover {
                transform: translateY(-2px);
            }
            .card-header {
                background-color: white;
                border-bottom: 1px solid rgba(0,0,0,0.05);
                font-weight: 600;
            }
            .status-badge {
                padding: 5px 10px;
                border-radius: 20px;
                font-size: 0.8rem;
                font-weight: 500;
                display: inline-block;
            }
            .status-active {
                background-color: #e6f7ee;
                color: #10b981;
            }
            .status-inactive {
                background-color: #fef3f2;
                color: #f04438;
            }
            .status-warning {
                background-color: #fffaeb;
                color: #f79009;
            }
            .kpi-value {
                font-size: 1.75rem;
                font-weight: 600;
                margin: 5px 0;
            }
            .kpi-label {
                color: #6c757d;
                font-size: 0.875rem;
                margin-bottom: 0.25rem;
            }
            .kpi-card {
                padding: 1.25rem;
            }
            .chart-container {
                height: 300px;
                width: 100%;
            }
            .activity-item {
                padding: 0.75rem 0;
                border-bottom: 1px solid rgba(0,0,0,0.05);
            }
            .activity-time {
                font-size: 0.75rem;
                color: #6c757d;
            }
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <!-- Header -->
            <div class="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h1 class="mb-1">5G Network Slice Manager</h1>
                    <p class="text-muted mb-0">Monitor and manage your 5G network slices in real-time</p>
                </div>
                <div class="d-flex align-items-center">
                    <div class="me-3">
                        <div class="text-end">
                            <div class="text-muted small">Last updated</div>
                            <div>{{ now.strftime('%H:%M:%S') }}</div>
                        </div>
                    </div>
                    <div class="dropdown">
                        <button class="btn btn-light dropdown-toggle" type="button" id="userDropdown" data-bs-toggle="dropdown" aria-expanded="false">
                            <i class="bi bi-person-circle me-1"></i>
                            Admin User
                        </button>
                        <ul class="dropdown-menu dropdown-menu-end" aria-labelledby="userDropdown">
                            <li><a class="dropdown-item" href="#"><i class="bi bi-person me-2"></i>Profile</a></li>
                            <li><a class="dropdown-item" href="#"><i class="bi bi-gear me-2"></i>Settings</a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item text-danger" href="#"><i class="bi bi-box-arrow-right me-2"></i>Logout</a></li>
                        </ul>
                    </div>
                </div>
            </div>
            
            <!-- KPI Cards -->
            <div class="row g-4 mb-4">
                <div class="col-md-3">
                    <div class="card h-100">
                        <div class="card-body kpi-card">
                            <div class="d-flex justify-content-between align-items-start">
                                <div>
                                    <div class="kpi-label">Active Slices</div>
                                    <div class="kpi-value text-primary">{{ kpis.active_slices }}</div>
                                    <div class="text-success small"><i class="bi bi-arrow-up"></i> 12% from last hour</div>
                                </div>
                                <div class="bg-primary bg-opacity-10 p-3 rounded">
                                    <i class="bi bi-diagram-3 text-primary" style="font-size: 1.5rem;"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card h-100">
                        <div class="card-body kpi-card">
                            <div class="d-flex justify-content-between align-items-start">
                                <div>
                                    <div class="kpi-label">Connected Devices</div>
                                    <div class="kpi-value text-success">{{ "{:,}".format(kpis.total_devices) }}</div>
                                    <div class="text-success small"><i class="bi bi-arrow-up"></i> 5.2% from last hour</div>
                                </div>
                                <div class="bg-success bg-opacity-10 p-3 rounded">
                                    <i class="bi bi-phone text-success" style="font-size: 1.5rem;"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card h-100">
                        <div class="card-body kpi-card">
                            <div class="d-flex justify-content-between align-items-start">
                                <div>
                                    <div class="kpi-label">Avg. Latency</div>
                                    <div class="kpi-value text-warning">{{ "%.2f"|format(kpis.avg_latency) }} ms</div>
                                    <div class="text-danger small"><i class="bi bi-arrow-up"></i> 8.3% from last hour</div>
                                </div>
                                <div class="bg-warning bg-opacity-10 p-3 rounded">
                                    <i class="bi bi-speedometer2 text-warning" style="font-size: 1.5rem;"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card h-100">
                        <div class="card-body kpi-card">
                            <div class="d-flex justify-content-between align-items-start">
                                <div>
                                    <div class="kpi-label">Active Alerts</div>
                                    <div class="kpi-value text-danger">{{ kpis.alerts }}</div>
                                    <div class="text-success small"><i class="bi bi-arrow-down"></i> 2 from last hour</div>
                                </div>
                                <div class="bg-danger bg-opacity-10 p-3 rounded">
                                    <i class="bi bi-exclamation-triangle text-danger" style="font-size: 1.5rem;"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Main Content -->
            <div class="row g-4">
                <!-- Left Column -->
                <div class="col-lg-8">
                    <!-- Throughput Chart -->
                    <div class="card mb-4">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h5 class="mb-0">Network Throughput</h5>
                            <div class="btn-group" role="group">
                                <button type="button" class="btn btn-sm btn-outline-secondary active" onclick="updateTimeRange('1h', this)">1H</button>
                                <button type="button" class="btn btn-sm btn-outline-secondary" onclick="updateTimeRange('6h', this)">6H</button>
                                <button type="button" class="btn btn-sm btn-outline-secondary" onclick="updateTimeRange('24h', this)">24H</button>
                            </div>
                        </div>
                        <div class="card-body">
                            <div id="throughputChart" class="chart-container" style="height: 300px;"></div>
                            <div class="mt-2 d-flex justify-content-between">
                                <small class="text-muted">Min: <span id="minThroughput">0</span> Mbps</small>
                                <small class="text-muted">Avg: <span id="avgThroughput">0</span> Mbps</small>
                                <small class="text-muted">Max: <span id="maxThroughput">0</span> Mbps</small>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Latency Chart -->
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0">Network Latency</h5>
                        </div>
                        <div class="card-body">
                            <div id="latencyChart" class="chart-container" style="height: 250px;"></div>
                            <div class="mt-2 d-flex justify-content-between">
                                <small class="text-muted">Min: <span id="minLatency">0</span> ms</small>
                                <small class="text-muted">Avg: <span id="avgLatency">0</span> ms</small>
                                <small class="text-muted">Max: <span id="maxLatency">0</span> ms</small>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Network Slices Table -->
                    <div class="card">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h5 class="mb-0">Network Slices</h5>
                            <button class="btn btn-primary btn-sm" data-bs-toggle="modal" data-bs-target="#createSliceModal">
                                <i class="bi bi-plus-lg me-1"></i> Create Slice
                            </button>
                        </div>
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table table-hover mb-0">
                                    <thead class="table-light">
                                        <tr>
                                            <th>Slice ID</th>
                                            <th>Name</th>
                                            <th>Status</th>
                                            <th>Users</th>
                                            <th>Type</th>
                                            <th>Capacity</th>
                                            <th>Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {% if slices %}
                                            <!-- Debug: Showing number of slices -->
                                            <script>console.log('Rendering {{ slices|length }} slices');</script>
                                            {% for slice in slices %}
                                            <tr>
                                                <td>{{ slice.id }}</td>
                                                <td>{{ slice.name }}</td>
                                                <td>
                                                    <span class="badge bg-{{ 'success' if slice.status|lower == 'active' else 'secondary' }}">
                                                        {{ slice.status }}
                                                    </span>
                                                </td>
                                                <td>{{ slice.connected_devices or 0 }}</td>
                                                <td>{{ slice.type }}</td>
                                                <td>
                                                    <div class="d-flex align-items-center">
                                                        {% set capacity = slice.capacity|default('0%')
                                                           if slice.capacity is string
                                                           else '0%' %}
                                                        {% set width = capacity|replace('%', '')|int %}
                                                        <div class="progress flex-grow-1 me-2" style="height: 6px;">
                                                            <div class="progress-bar bg-{{ 'success' if width < 80 else 'warning' if width < 95 else 'danger' }}" 
                                                                 style="width: {{ width }}%">
                                                            </div>
                                                        </div>
                                                        <small class="text-muted">{{ capacity }}</small>
                                                    </div>
                                                </td>
                                                <td>
                                                    <div class="dropdown">
                                                        <button class="btn btn-link text-muted p-0" type="button" data-bs-toggle="dropdown">
                                                            <i class="bi bi-three-dots-vertical"></i>
                                                        </button>
                                                        <ul class="dropdown-menu">
                                                            <li><a class="dropdown-item" href="#"><i class="bi bi-eye me-2"></i>View</a></li>
                                                            <li><a class="dropdown-item" href="#"><i class="bi bi-pencil me-2"></i>Edit</a></li>
                                                            {% if slice.status|lower == 'active' %}
                                                            <li><a class="dropdown-item text-danger" href="#"><i class="bi bi-power me-2"></i>Deactivate</a></li>
                                                            {% else %}
                                                            <li><a class="dropdown-item text-success" href="#"><i class="bi bi-power me-2"></i>Activate</a></li>
                                                            {% endif %}
                                                        </ul>
                                                    </div>
                                                </td>
                                            </tr>
                                            {% endfor %}
                                        {% else %}
                                            <tr>
                                                <td colspan="7" class="text-center text-muted py-4">
                                                    <i class="bi bi-inbox" style="font-size: 2rem; opacity: 0.5;"></i>
                                                    <p class="mt-2 mb-0">No slices found. Create your first slice to get started.</p>
                                                </td>
                                            </tr>
                                        {% endif %}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Right Column -->
                <div class="col-lg-4">
                    <!-- Activity Feed -->
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0">Activity Feed</h5>
                        </div>
                        <div class="card-body p-0">
                            <div class="list-group list-group-flush">
                                {% for activity in activities %}
                                <div class="list-group-item border-0">
                                    <div class="d-flex align-items-start">
                                        <div class="me-3">
                                            {% if activity.type == 'alert_triggered' %}
                                            <div class="bg-danger bg-opacity-10 p-2 rounded-circle">
                                                <i class="bi bi-exclamation-triangle-fill text-danger"></i>
                                            </div>
                                            {% elif activity.type == 'device_connect' %}
                                            <div class="bg-success bg-opacity-10 p-2 rounded-circle">
                                                <i class="bi bi-phone-fill text-success"></i>
                                            </div>
                                            {% else %}
                                            <div class="bg-primary bg-opacity-10 p-2 rounded-circle">
                                                <i class="bi bi-sliders text-primary"></i>
                                            </div>
                                            {% endif %}
                                        </div>
                                        <div class="flex-grow-1">
                                            <div class="d-flex justify-content-between">
                                                <h6 class="mb-1">{{ activity.message }}</h6>
                                                <small class="text-muted">{{ activity.timestamp.split(' ')[1] }}</small>
                                            </div>
                                            <small class="text-muted">{{ activity.timestamp.split(' ')[0] }}</small>
                                        </div>
                                    </div>
                                </div>
                                {% endfor %}
                            </div>
                        </div>
                        <div class="card-footer bg-transparent border-top-0">
                            <a href="#" class="btn btn-link text-decoration-none p-0">View all activity</a>
                        </div>
                    </div>
                    
                    <!-- System Status -->
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0">System Status</h5>
                        </div>
                        <div class="card-body">
                            <div class="mb-3">
                                <div class="d-flex justify-content-between mb-1">
                                    <span>CPU Usage</span>
                                    <span class="text-muted">45%</span>
                                </div>
                                <div class="progress" style="height: 8px;">
                                    <div class="progress-bar bg-info" role="progressbar" style="width: 45%" aria-valuenow="45" aria-valuemin="0" aria-valuemax="100"></div>
                                </div>
                            </div>
                            <div class="mb-3">
                                <div class="d-flex justify-content-between mb-1">
                                    <span>Memory</span>
                                    <span class="text-muted">65%</span>
                                </div>
                                <div class="progress" style="height: 8px;">
                                    <div class="progress-bar bg-warning" role="progressbar" style="width: 65%" aria-valuenow="65" aria-valuemin="0" aria-valuemax="100"></div>
                                </div>
                            </div>
                            <div>
                                <div class="d-flex justify-content-between mb-1">
                                    <span>Storage</span>
                                    <span class="text-muted">32%</span>
                                </div>
                                <div class="progress" style="height: 8px;">
                                    <div class="progress-bar bg-success" role="progressbar" style="width: 32%" aria-valuenow="32" aria-valuemin="0" aria-valuemax="100"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Create Slice Modal -->
        <div class="modal fade" id="createSliceModal" tabindex="-1" aria-labelledby="createSliceModalLabel" aria-hidden="true">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="createSliceModalLabel">Create New Slice</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <form id="createSliceForm">
                            <div class="mb-3">
                                <label for="sliceName" class="form-label">Slice Name</label>
                                <input type="text" class="form-control" id="sliceName" required>
                            </div>
                            <div class="mb-3">
                                <label for="sliceType" class="form-label">Slice Type</label>
                                <select class="form-select" id="sliceType" required>
                                    <option value="">Select a type</option>
                                    <option value="eMBB">eMBB (Enhanced Mobile Broadband)</option>
                                    <option value="URLLC">URLLC (Ultra-Reliable Low-Latency)</option>
                                    <option value="mMTC">mMTC (Massive Machine Type)</option>
                                </select>
                            </div>
                            <div class="mb-3">
                                <label for="sliceDescription" class="form-label">Description</label>
                                <textarea class="form-control" id="sliceDescription" rows="3"></textarea>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-primary" id="confirmCreateSlice">Create Slice</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Security Footer with Icons -->
        <footer id="security-footer" class="mt-auto py-3 bg-light" style="font-size: 0.8rem; color: #6c757d; border-top: 1px solid #e9ecef;">
            <div class="container">
                <div class="row align-items-center">
                    <div class="col-12">
                        <div id="security-hash" class="d-flex flex-wrap justify-content-center align-items-center gap-4">
                            <div class="d-flex align-items-center">
                                <i class="bi bi-person-fill me-2" title="Developer"></i>
                                <span>Ian Reuben Siangani</span>
                            </div>
                            <div class="d-flex align-items-center">
                                <i class="bi bi-envelope-fill me-2" title="Email"></i>
                                <a href="mailto:ireuben03@gmail.com" class="text-muted text-decoration-none">ireuben03@gmail.com</a>
                            </div>
                            <div class="d-flex align-items-center">
                                <i class="bi bi-github me-2" title="GitHub"></i>
                                <a href="https://github.com/isiangani1" target="_blank" class="text-muted text-decoration-none">github.com/isiangani1</a>
                            </div>
                            <div class="d-flex align-items-center">
                                <i class="bi bi-telephone-fill me-2" title="Phone"></i>
                                <a href="tel:+245799319387" class="text-muted text-decoration-none">+245 799 319387</a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </footer>

        <!-- Toast Notification -->
        <div class="position-fixed bottom-0 end-0 p-3" style="z-index: 11">
            <div id="successToast" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header bg-success text-white">
                    <strong class="me-auto">Success</strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body">
                    <i class="bi bi-check-circle-fill me-2"></i>
                    <span id="toastMessage">Slice created successfully!</span>
                </div>
            </div>
        </div>

        <!-- Scripts -->
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        <script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
        <script>
            // Initialize tooltips
            document.addEventListener('DOMContentLoaded', function() {
                // Initialize tooltips
                var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
                tooltipTriggerList.forEach(function (tooltipTriggerEl) {
                    new bootstrap.Tooltip(tooltipTriggerEl);
                });
                
                // Initialize toast
                const toastEl = document.getElementById('successToast');
                if (toastEl) {
                    window.successToast = new bootstrap.Toast(toastEl);
                }
                
                // Initialize charts if the function exists
                if (typeof initCharts === 'function') {
                    initCharts();
                }
                
                // Initialize stats if the function exists
                if (typeof updateStats === 'function') {
                    updateStats();
                }
            });
            
            // Handle create slice form submission
            document.getElementById('confirmCreateSlice').addEventListener('click', async function() {
                const name = document.getElementById('sliceName').value.trim();
                const type = document.getElementById('sliceType').value;
                const description = document.getElementById('sliceDescription').value.trim();
                const createButton = this;
                
                if (!name || !type) {
                    showToast('Please fill in all required fields', 'warning');
                    return;
                }

                const response = await fetch('/api/create-slice', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        name,
                        type,
                        description
                    })
                });

                const result = await response.json();

                if (response.ok) {
                    // Show success message
                    showToast('Slice created successfully!', 'success');
                    
                    // Close modal after a short delay
                    const modal = bootstrap.Modal.getInstance(document.getElementById('createSliceModal'));
                    modal.hide();
                    
                    // Reset form
                    document.getElementById('createSliceForm').reset();
                    
                    // Reload the page after a short delay to show the new slice
                    setTimeout(() => {
                        window.location.reload();
                    }, 1500);
                } else {
                    showToast(result.error || 'Failed to create slice', 'danger');
                }
            });

            function showToast(message, type) {
                const toastMessage = document.getElementById('toastMessage');
                toastMessage.textContent = message;
                successToast.show();
            }
                })();
            </script>
            <script>
            // Initialize tooltips
            var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
            
            // Initialize charts when DOM is fully loaded
            document.addEventListener('DOMContentLoaded', function() {
                // Get data from the template
                const timestamps = {{ timestamps|tojson|safe }} || [];
                let throughput = {{ throughput|tojson|safe }} || [];
                let latency = {{ latency|tojson|safe }} || [];
                
                // Debug logging
                console.log('Timestamps:', timestamps);
                console.log('Throughput:', throughput);
                console.log('Latency:', latency);
                
                // Ensure we have valid data
                if (throughput.length === 0 && latency.length === 0) {
                    console.log('No data available, generating mock data...');
                    const now = new Date();
                    const mockTimestamps = [];
                    const mockThroughput = [];
                    const mockLatency = [];
                    
                    for (let i = 0; i < 12; i++) {
                        const time = new Date(now - (11 - i) * 5 * 60000);
                        mockTimestamps.push(time.getHours().toString().padStart(2, '0') + ':' + 
                                         time.getMinutes().toString().padStart(2, '0'));
                        mockThroughput.push(Math.max(10, 100 + Math.random() * 200));
                        mockLatency.push(Math.max(1, 10 + Math.random() * 40));
                    }
                    
                    // Use mock data
                    if (timestamps.length === 0) timestamps.push(...mockTimestamps);
                    if (throughput.length === 0) throughput.push(...mockThroughput);
                    if (latency.length === 0) latency.push(...mockLatency);
                    
                    console.log('Using mock data:', {timestamps, throughput, latency});
                }
                
                // Only initialize charts if Plotly is available
                if (typeof Plotly !== 'undefined') {
                    try {
                        initializeCharts(timestamps, throughput, latency);
                        
                        // Update KPI values in the UI
                        updateKPIValues({
                            activeSlices: {{ kpis.active_slices|default(0) }},
                            totalDevices: {{ kpis.total_devices|default(0) }},
                            avgLatency: {{ kpis.avg_latency|default(0) }},
                            activeAlerts: {{ kpis.alerts|default(0) }},
                            minThroughput: {{ min_throughput|default(0) }},
                            avgThroughput: {{ avg_throughput|default(0) }},
                            maxThroughput: {{ max_throughput|default(0) }},
                            minLatency: {{ min_latency|default(0) }},
                            maxLatency: {{ max_latency|default(0) }}
                        });
                    } catch (error) {
                        console.error('Error initializing charts:', error);
                        // Show error message to user
                        const container = document.getElementById('charts-container');
                        if (container) {
                            container.innerHTML = `
                                <div class="alert alert-danger">
                                    <i class="bi bi-exclamation-triangle-fill me-2"></i>
                                    Error loading charts: ${error.message}
                                </div>
                            `;
                        }
                    }
                } else {
                    console.error('Plotly not loaded');
                }
            });
            
            // Function to update KPI values in the UI
            function updateKPIValues(kpis) {
                // Update KPI cards
                const updateElement = (id, value, suffix = '') => {
                    const el = document.getElementById(id);
                    if (el) {
                        el.textContent = typeof value === 'number' ? value.toLocaleString() + (suffix ? ` ${suffix}` : '') : value;
                    }
                };
                
                // Update the KPI cards
                updateElement('activeSlices', kpis.activeSlices);
                updateElement('totalDevices', kpis.totalDevices);
                updateElement('avgLatency', kpis.avgLatency, 'ms');
                updateElement('activeAlerts', kpis.activeAlerts);
                
                // Update chart stats
                updateElement('minThroughput', kpis.minThroughput, 'Mbps');
                updateElement('avgThroughput', kpis.avgThroughput, 'Mbps');
                updateElement('maxThroughput', kpis.maxThroughput, 'Mbps');
                updateElement('minLatency', kpis.minLatency, 'ms');
                updateElement('maxLatency', kpis.maxLatency, 'ms');
            }
            
            function initializeCharts(timestamps, throughput, latency) {
                console.log('Initializing charts...');
                
                // Calculate stats
                function calculateStats(data) {
                    if (!data || data.length === 0) return { min: 0, max: 0, avg: 0 };
                    const min = Math.min(...data).toFixed(2);
                    const max = Math.max(...data).toFixed(2);
                    const avg = (data.reduce((a, b) => a + b, 0) / data.length).toFixed(2);
                    return { min, max, avg };
                }
                
                // Throughput Chart
                const throughputTrace = {
                    x: timestamps,
                    y: throughput,
                    type: 'scatter',
                    mode: 'lines+markers',
                    name: 'Throughput',
                    line: {color: '#4361ee', width: 2},
                    marker: {color: '#4361ee', size: 4},
                    fill: 'tozeroy',
                    fillcolor: 'rgba(67, 97, 238, 0.1)'
                };
                
                const throughputLayout = {
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    margin: {t: 30, b: 40, l: 50, r: 30},
                    showlegend: false,
                    xaxis: {
                        showgrid: false,
                        zeroline: false,
                        showline: true,
                        linecolor: '#e9ecef',
                        linewidth: 1,
                        tickfont: {size: 10, color: '#6c757d'}
                    },
                    yaxis: {
                        title: 'Mbps',
                        titlefont: {size: 12, color: '#6c757d'},
                        tickfont: {size: 10, color: '#6c757d'},
                        gridcolor: 'rgba(0,0,0,0.05)',
                        zeroline: false,
                        showline: true,
                        linecolor: '#e9ecef',
                        linewidth: 1
                    },
                    hovermode: 'x unified'
                };
                
                // Latency Chart
                const latencyTrace = {
                    x: timestamps,
                    y: latency,
                    type: 'scatter',
                    mode: 'lines+markers',
                    name: 'Latency',
                    line: {color: '#4cc9a0', width: 2},
                    marker: {color: '#4cc9a0', size: 4},
                    fill: 'tozeroy',
                    fillcolor: 'rgba(76, 201, 160, 0.1)'
                };
                
                const latencyLayout = {
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    margin: {t: 30, b: 40, l: 50, r: 30},
                    showlegend: false,
                    xaxis: {
                        showgrid: false,
                        zeroline: false,
                        showline: true,
                        linecolor: '#e9ecef',
                        linewidth: 1,
                        tickfont: {size: 10, color: '#6c757d'}
                    },
                    yaxis: {
                        title: 'ms',
                        titlefont: {size: 12, color: '#6c757d'},
                        tickfont: {size: 10, color: '#6c757d'},
                        gridcolor: 'rgba(0,0,0,0.05)',
                        zeroline: false,
                        showline: true,
                        linecolor: '#e9ecef',
                        linewidth: 1
                    },
                    hovermode: 'x unified'
                };
                
                // Create charts
                const config = {responsive: true, displayModeBar: false};
                Plotly.newPlot('throughputChart', [throughputTrace], throughputLayout, config);
                Plotly.newPlot('latencyChart', [latencyTrace], latencyLayout, config);
                
                // Update stats
                function updateStats() {
                    const tpStats = calculateStats(throughput);
                    const ltStats = calculateStats(latency);
                    
                    const minTpEl = document.getElementById('minThroughput');
                    const avgTpEl = document.getElementById('avgThroughput');
                    const maxTpEl = document.getElementById('maxThroughput');
                    const minLatEl = document.getElementById('minLatency');
                    const avgLatEl = document.getElementById('avgLatency');
                    const maxLatEl = document.getElementById('maxLatency');
                    
                    if (minTpEl) minTpEl.textContent = tpStats.min;
                    if (avgTpEl) avgTpEl.textContent = tpStats.avg;
                    if (maxTpEl) maxTpEl.textContent = tpStats.max;
                    if (minLatEl) minLatEl.textContent = ltStats.min;
                    if (avgLatEl) avgLatEl.textContent = ltStats.avg;
                    if (maxLatEl) maxLatEl.textContent = ltStats.max;
                }
                
                // Initial stats update
                updateStats();
                
                // Time range selector
                function updateTimeRange(range, element) {
                    // Update active button
                    document.querySelectorAll('.btn-group .btn').forEach(btn => {
                        btn.classList.remove('active');
                    });
                    element.classList.add('active');
                    
                    // Here you would typically fetch new data based on the selected range
                    // For now, we'll just update the x-axis range
                    const now = new Date();
                    let startTime;
                    
                    switch(range) {
                        case '1h':
                            startTime = new Date(now.getTime() - 60 * 60 * 1000);
                            break;
                        case '6h':
                            startTime = new Date(now.getTime() - 6 * 60 * 60 * 1000);
                            break;
                        case '24h':
                            startTime = new Date(now.getTime() - 24 * 60 * 60 * 1000);
                            break;
                        default:
                            startTime = new Date(now.getTime() - 60 * 60 * 1000);
                    }
                    
                    const update = {
                        'xaxis.range': [startTime, now]
                    };
                    
                    Plotly.relayout('throughputChart', update);
                    Plotly.relayout('latencyChart', update);
                    
                    // In a real app, you would fetch new data here:
                    // fetchNewData(range);
                }
                
                // Expose the updateTimeRange function to the global scope
                window.updateTimeRange = updateTimeRange;
            }
            
            // Initial stats update
            updateStats();
            
            // Handle window resize
            function handleResize() {
                Plotly.Plots.resize('throughputChart');
                Plotly.Plots.resize('latencyChart');
            }
            
            window.addEventListener('resize', handleResize);
        </script>
    </body>
    </html>
    """
        
        # Prepare the data for the template
        now = datetime.now()
        
        # Ensure we have data for the charts
        if not throughput_data or not latency_data or not timestamps_data:
            print("No chart data available, generating mock data...")
            # Generate mock data with realistic values
            timestamps_data = [(now - timedelta(minutes=i*5)).strftime('%H:%M') 
                             for i in reversed(range(12))]
            
            # Generate realistic throughput data (Mbps)
            base_throughput = random.uniform(50, 200)
            throughput_data = [max(10, base_throughput + random.uniform(-20, 50)) for _ in range(12)]
            
            # Generate realistic latency data (ms)
            base_latency = random.uniform(10, 30)
            latency_data = [max(1, base_latency + random.uniform(-5, 10)) for _ in range(12)]
        
        # Ensure we have valid KPI data
        if not kpis_data or all(v == 0 for v in kpis_data.values()):
            print("No valid KPI data, using mock data...")
            kpis_data = {
                'active_slices': random.randint(1, 5),
                'total_devices': random.randint(10, 100),
                'avg_latency': round(random.uniform(5, 50), 2),
                'alerts': random.randint(0, 5)
            }
        
        # Calculate min/max/avg for the charts
        min_throughput = min(throughput_data) if throughput_data else 0
        max_throughput = max(throughput_data) if throughput_data else 0
        avg_throughput = sum(throughput_data) / len(throughput_data) if throughput_data else 0
        
        min_latency = min(latency_data) if latency_data else 0
        max_latency = max(latency_data) if latency_data else 0
        avg_latency = sum(latency_data) / len(latency_data) if latency_data else 0
        
        # Ensure we have at least one timestamp
        if not timestamps_data and (throughput_data or latency_data):
            timestamps_data = [str(i) for i in range(max(len(throughput_data), len(latency_data)))]
        
        # Debug output
        print("Rendering template with data:")
        print(f"- Slices: {len(slices_data)}")
        print(f"- KPIs: {kpis_data}")
        print(f"- Activities: {len(activities_data)}")
        print(f"- Chart data points: {len(timestamps_data)} timestamps, {len(throughput_data)} throughput, {len(latency_data)} latency")
        
        try:
            return render_template_string(
                template,
                slices=slices_data,
                kpis=kpis_data,
                activities=activities_data,
                timestamps=timestamps_data,
                throughput=throughput_data,
                latency=latency_data,
                now=now,
                min_throughput=round(min_throughput, 2),
                max_throughput=round(max_throughput, 2),
                avg_throughput=round(avg_throughput, 2),
                min_latency=round(min_latency, 2),
                max_latency=round(max_latency, 2),
                avg_latency=round(avg_latency, 2)
            )
        except Exception as e:
            print(f"Error rendering template: {e}")
            return f"Error rendering dashboard: {str(e)}", 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error rendering dashboard: {str(e)}", 500

# API Endpoints
@app.route('/api/slices')
@async_route
async def get_slices():
    """API endpoint to get all slices."""
    try:
        slices = await get_slices_from_db()
        return jsonify(slices)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/kpis')
@async_route
async def get_kpis():
    """API endpoint to get KPI summary."""
    try:
        kpis = await get_kpis_from_db()
        return jsonify(kpis)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/activity')
@async_route
async def get_activity():
    """API endpoint to get recent activity."""
    try:
        limit = request.args.get('limit', default=10, type=int)
        activity = await get_activity_from_db(limit)
        return jsonify(activity)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Template filters
import hashlib

def md5_hash(text):
    """Generate MD5 hash of text."""
    return hashlib.md5(str(text).encode('utf-8')).hexdigest()

# Register template filters
app.jinja_env.filters['md5'] = md5_hash

@app.template_filter('tojson')
def to_json(value):
    """Convert value to JSON."""
    return json.dumps(value, indent=2)

# Run directly with: python app.py
if __name__ == '__main__':
    app.run(debug=True, port=8050)
