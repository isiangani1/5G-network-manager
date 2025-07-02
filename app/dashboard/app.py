import os
from flask import Flask, render_template_string, jsonify, redirect, url_for, request, json
from datetime import datetime, timedelta
import random
import asyncio
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
    try:
        async with get_db_session() as session:
            async with session.begin():
                # Query slices with their latest KPIs
                result = await session.execute(
                    select(Slice)
                    .order_by(Slice.created_at.desc())
                )
                slices = result.scalars().all()
                
                # Convert to list of dicts
                return [{
                    'id': slice.id,
                    'name': slice.name,
                    'type': slice.type,
                    'status': slice.status,
                    'created_at': slice.created_at,
                    'updated_at': slice.updated_at,
                    'description': slice.description
                } for slice in slices]
    except Exception as e:
        print(f"Error in get_slices_from_db: {e}")
        import traceback
        traceback.print_exc()
        return []

async def get_kpis_from_db() -> Dict[str, Any]:
    """Retrieve KPI summary from the database."""
    try:
        async with get_db_session() as session:
            async with session.begin():
                # Get total slices
                result = await session.execute(select(func.count(Slice.id)))
                total_slices = result.scalar() or 0
                
                # Get active slices
                result = await session.execute(
                    select(func.count(Slice.id))
                    .where(Slice.status == 'Active')
                )
                active_slices = result.scalar() or 0
                
                # Get average latency
                result = await session.execute(select(func.avg(SliceKPI.latency)))
                avg_latency = round(float(result.scalar() or 0), 2)
                
                # Get average throughput
                result = await session.execute(select(func.avg(SliceKPI.throughput)))
                avg_throughput = round(float(result.scalar() or 0), 2)
                
                return {
                    'total_slices': total_slices,
                    'active_slices': active_slices,
                    'avg_latency': avg_latency,
                    'avg_throughput': avg_throughput
                }
    except Exception as e:
        print(f"Error in get_kpis_from_db: {e}")
        import traceback
        traceback.print_exc()
        return {
            'total_slices': 0,
            'active_slices': 0,
            'avg_latency': 0,
            'avg_throughput': 0
        }

async def get_activity_from_db(limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieve recent activity from the database."""
    try:
        session_gen = get_db_session()
        session = await anext(session_gen)
        try:
            # Explicitly select only the columns that exist in the Alert model
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
                    Alert.device_id,
                    Alert.context
                )
                .order_by(Alert.timestamp.desc())
                .limit(limit)
            )
            alerts = result.fetchall()
            
            # Convert to list of dicts
            return [{
                'id': row[0],  # id
                'timestamp': row[1],  # timestamp
                'level': row[2],  # level
                'message': row[3],  # message
                'resolved': row[4],  # resolved
                'resolved_at': row[5],  # resolved_at
                'entity_type': row[6],  # entity_type
                'entity_id': row[7],  # entity_id
                'device_id': row[8],  # device_id
                'context': row[9]  # context
            } for row in alerts]
        finally:
            await session.close()
    except Exception as e:
        print(f"Error in get_activity_from_db: {e}")
        import traceback
        traceback.print_exc()
        return []

async def get_throughput_latency_from_db(slice_id: str, hours: int = 24) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Retrieve throughput and latency data for a slice."""
    session = None
    try:
        session_gen = get_db_session()
        session = await anext(session_gen)
        
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
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
        data_points = result.fetchall()
        
        # Format data for charts
        throughput_data = [{
            'time': point.time,
            'value': float(point.avg_throughput or 0)
        } for point in data_points]
        
        latency_data = [{
            'time': point.time,
            'value': float(point.avg_latency or 0)
        } for point in data_points]
        
        return throughput_data, latency_data
        
    except Exception as e:
        print(f"Error in get_throughput_latency_from_db: {e}")
        import traceback
        traceback.print_exc()
        return [], []
    finally:
        if session:
            await session.close()

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Register template filters
    app.jinja_env.filters['md5'] = md5_hash
    app.jinja_env.filters['to_json'] = to_json
    
    return app

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
            print(f"Retrieved {len(slices_from_db)} slices")
            
            # Map slices to the format expected by the template
            slices_data = []
            for slice_item in slices_from_db:
                slices_data.append({
                    'id': slice_item.get('id', ''),
                    'name': slice_item.get('name', 'Unnamed Slice'),
                    'status': slice_item.get('status', 'Inactive'),
                    'users': slice_item.get('user_count', 0),
                    'type': slice_item.get('type', 'Unknown'),
                    'capacity': f"{slice_item.get('utilization', 0)}%"
                })
            
            print("Fetching KPIs...")
            kpis_from_db = await get_kpis_from_db()
            
            # Map the database KPIs to the structure expected by the template
            if kpis_from_db:
                kpis_data = {
                    'active_slices': kpis_from_db.get('active_slices', 0),
                    'total_devices': kpis_from_db.get('total_devices', 0),
                    'avg_latency': float(kpis_from_db.get('avg_latency', 0.0)),
                    'alerts': kpis_from_db.get('alerts', 0)
                }
            
            print(f"Retrieved KPIs: {kpis_data}")
            
            print("Fetching recent activity...")
            activity_from_db = await get_activity_from_db(limit=10)
            activities_data = []
            
            # Map activity data to the format expected by the template
            for activity in activity_from_db:
                activities_data.append({
                    'type': 'alert_triggered' if activity.get('level') == 'ERROR' else 'device_connect',
                    'message': activity.get('message', 'No message'),
                    'timestamp': activity.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                })
            
            print(f"Retrieved {len(activities_data)} activities")
            
            # Generate mock data for charts if no real data
            if slices_data:
                try:
                    # Get the first slice's data for the charts
                    first_slice_id = slices_data[0]['id']
                    print(f"Fetching throughput/latency data for slice {first_slice_id}...")
                    result = await get_throughput_latency_from_db(first_slice_id)
                    
                    if isinstance(result, tuple) and len(result) == 2:
                        throughput_data, latency_data = result
                        # Generate timestamps for the data points
                        now = datetime.now()
                        timestamps_data = [(now - timedelta(minutes=i*5)).strftime('%H:%M') 
                                         for i in reversed(range(len(throughput_data)))]
                        print(f"Retrieved {len(throughput_data)} throughput and {len(latency_data)} latency data points")
                except Exception as e:
                    print(f"Error getting throughput/latency data: {e}")
                    # Generate mock data if there's an error
                    timestamps_data = [(datetime.now() - timedelta(minutes=i*5)).strftime('%H:%M') 
                                    for i in reversed(range(12))]
                    throughput_data = [random.uniform(100, 1000) for _ in range(12)]
                    latency_data = [random.uniform(5, 50) for _ in range(12)]
            else:
                # Generate mock data if no slices
                timestamps_data = [(datetime.now() - timedelta(minutes=i*5)).strftime('%H:%M') 
                                for i in reversed(range(12))]
                throughput_data = [random.uniform(100, 1000) for _ in range(12)]
                latency_data = [random.uniform(5, 50) for _ in range(12)]
                
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
                            <button class="btn btn-primary btn-sm">
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
                                        {% for slice in slices %}
                                        <tr>
                                            <td>{{ slice.id }}</td>
                                            <td>{{ slice.name }}</td>
                                            <td>
                                                <span class="status-badge status-{{ slice.status|lower }}">
                                                    {{ slice.status }}
                                                </span>
                                            </td>
                                            <td>{{ slice.users }}</td>
                                            <td>{{ slice.type }}</td>
                                            <td>
                                                <div class="d-flex align-items-center">
                                                    <div class="progress flex-grow-1 me-2" style="height: 6px;">
                                                        <div class="progress-bar bg-{{ 'success' if slice.status == 'Active' else 'secondary' }}" 
                                                             style="width: {{ slice.capacity.split('%')[0] }}%">
                                                        </div>
                                                    </div>
                                                    <small class="text-muted">{{ slice.capacity }}</small>
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
                                                        {% if slice.status == 'Active' %}
                                                        <li><a class="dropdown-item text-danger" href="#"><i class="bi bi-power me-2"></i>Deactivate</a></li>
                                                        {% else %}
                                                        <li><a class="dropdown-item text-success" href="#"><i class="bi bi-power me-2"></i>Activate</a></li>
                                                        {% endif %}
                                                    </ul>
                                                </div>
                                            </td>
                                        </tr>
                                        {% endfor %}
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
            </footer>

            <!-- Scripts -->
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
            <script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
            <script>
                // Security Check - Do not remove or modify
                (function() {
                    // Obfuscated security check
                    function _0x1a2b3c() {
                        const _0x123456 = document.getElementById('security-hash');
                        if (!_0x123456 || !_0x123456.textContent.includes('Ian Reuben Siangani') || 
                            !_0x123456.textContent.includes('ireuben03@gmail.com') ||
                            !_0x123456.textContent.includes('github.com/isiangani1') ||
                            !_0x123456.textContent.includes('+245 799 319387')) {
                            // If footer is tampered with, break the app
                            console.error('Security violation detected!');
                            document.body.innerHTML = '<div style="text-align:center;padding:50px;color:red;"><h1>Security Violation</h1><p>This application has been disabled due to unauthorized modifications.</p></div>';
                            // Prevent any further JavaScript execution
                            window.stop();
                            throw new Error('Security violation');
                        }
                    }
                    // Run check after everything is loaded
                    window.addEventListener('load', function() {
                        // Give the page a moment to fully render
                        setTimeout(_0x1a2b3c, 1000);
                        setInterval(_0x1a2b3c, 10000); // Check every 10 seconds
                    });
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
                const timestamps = {{ timestamps|tojson|safe }} || [];
                const throughput = {{ throughput|tojson|safe }} || [];
                const latency = {{ latency|tojson|safe }} || [];
                
                // Debug logging
                console.log('Timestamps:', timestamps);
                console.log('Throughput:', throughput);
                console.log('Latency:', latency);
                
                // Only initialize charts if Plotly is available
                if (typeof Plotly !== 'undefined') {
                    initializeCharts(timestamps, throughput, latency);
                } else {
                    console.error('Plotly not loaded');
                }
            });
            
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
        
        # Calculate min/max/avg for the charts
        min_throughput = min(throughput_data) if throughput_data else 0
        max_throughput = max(throughput_data) if throughput_data else 0
        avg_throughput = sum(throughput_data) / len(throughput_data) if throughput_data else 0
        
        min_latency = min(latency_data) if latency_data else 0
        max_latency = max(latency_data) if latency_data else 0
        avg_latency = sum(latency_data) / len(latency_data) if latency_data else 0
        
        return render_template_string(
            template,
            slices=slices_data,
            kpis=kpis_data,
            activities=activities_data,
            timestamps=timestamps_data,
            throughput=throughput_data,
            latency=latency_data,
            now=now,
            min_throughput=min_throughput,
            max_throughput=max_throughput,
            avg_throughput=avg_throughput,
            min_latency=min_latency,
            max_latency=max_latency,
            avg_latency=avg_latency
        )
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
