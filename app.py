from flask import Flask, render_template_string, jsonify, redirect, url_for
from datetime import datetime, timedelta
import random
import json
from typing import List, Dict, Any, Tuple

app = Flask(__name__)

# Constants
SLICE_TYPES = ["eMBB", "URLLC", "mMTC", "V2X", "Industrial IoT"]
STATUS_COLORS = {
    "Active": "success",
    "Inactive": "secondary",
    "Warning": "warning",
    "Error": "danger"
}

# Mock data generation functions
def generate_mock_slices() -> List[Dict[str, Any]]:
    slice_types = ['eMBB', 'URLLC', 'mMTC', 'V2X', 'IoT']
    statuses = ['Active', 'Inactive', 'Degraded', 'Maintenance']
    slices = []
    
    for i in range(1, 11):
        slice_type = random.choice(slice_types)
        status = random.choice(statuses)
        slices.append({
            'id': f'slice-{i:03d}',
            'name': f'{slice_type} Slice {i}',
            'type': slice_type,
            'status': status,
            'users': random.randint(10, 5000) if status == 'Active' else 0,
            'capacity': f'{random.randint(10, 100)}%',
            'latency': f'{random.uniform(1.0, 50.0):.2f} ms',
            'throughput': f'{random.uniform(100, 1000):.1f} Mbps',
            'last_updated': (datetime.now() - timedelta(minutes=random.randint(1, 60))).strftime('%Y-%m-%d %H:%M:%S')
        })
    return slices

def generate_mock_kpis() -> Dict[str, Any]:
    return {
        'active_slices': random.randint(3, 8),
        'total_slices': 10,
        'total_devices': random.randint(5000, 15000),
        'avg_latency': random.uniform(10.0, 50.0),
        'avg_throughput': random.uniform(200.0, 800.0),
        'alerts': random.randint(0, 5),
        'slice_utilization': random.randint(30, 95),
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

def generate_mock_throughput_latency() -> Tuple[List[str], List[float], List[float]]:
    now = datetime.now()
    timestamps = [(now - timedelta(minutes=i)).strftime('%H:%M') for i in range(60, -1, -1)]
    throughput = [random.uniform(100, 1000) for _ in range(61)]
    latency = [random.uniform(1.0, 50.0) for _ in range(61)]
    return timestamps, throughput, latency

def generate_mock_activity(count: int = 10) -> List[Dict[str, str]]:
    activities = []
    activity_types = ['slice_created', 'slice_modified', 'device_connect', 'alert_triggered', 'config_updated']
    slice_ids = [f'slice-{i:03d}' for i in range(1, 11)]
    
    for i in range(count):
        activity_type = random.choice(activity_types)
        timestamp = (datetime.now() - timedelta(minutes=random.randint(1, 120))).strftime('%Y-%m-%d %H:%M:%S')
        
        if activity_type == 'slice_created':
            message = f"New network slice {random.choice(slice_ids)} created"
        elif activity_type == 'slice_modified':
            message = f"Configuration updated for slice {random.choice(slice_ids)}"
        elif activity_type == 'device_connect':
            message = f"New device connected to slice {random.choice(slice_ids)}"
        elif activity_type == 'alert_triggered':
            message = f"Alert: High latency detected on slice {random.choice(slice_ids)}"
        else:
            message = "System configuration updated"
            
        activities.append({
            'id': f'act-{i+1:03d}',
            'type': activity_type,
            'message': message,
            'timestamp': timestamp,
            'severity': random.choice(['info', 'warning', 'error'])
        })
    
    return sorted(activities, key=lambda x: x['timestamp'], reverse=True)

# Routes
@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    slices_data = generate_mock_slices()
    kpis_data = generate_mock_kpis()
    timestamps_data, throughput_data, latency_data = generate_mock_throughput_latency()
    activities_data = generate_mock_activity(10)
    
    return render_template_string("""
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
        
        <!-- Scripts -->
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            // Initialize tooltips
            var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
            
            // Initialize charts
            const timestamps = {{ timestamps|tojson|safe }};
            const throughput = {{ throughput|tojson|safe }};
            const latency = {{ latency|tojson|safe }};
            
            // Calculate stats
            function calculateStats(data) {
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
                margin: {t: 10, b: 40, l: 50, r: 20},
                showlegend: false,
                xaxis: {
                    showgrid: false,
                    zeroline: false,
                    showline: true,
                    linecolor: '#e9ecef',
                    linewidth: 1
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
                margin: {t: 10, b: 40, l: 50, r: 20},
                showlegend: false,
                xaxis: {
                    showgrid: false,
                    zeroline: false,
                    showline: true,
                    linecolor: '#e9ecef',
                    linewidth: 1
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
            
            const config = {
                responsive: true,
                displayModeBar: false,
                scrollZoom: true
            };
            
            // Initialize charts
            Plotly.newPlot('throughputChart', [throughputTrace], throughputLayout, config);
            Plotly.newPlot('latencyChart', [latencyTrace], latencyLayout, config);
            
            // Update stats
            function updateStats() {
                const tpStats = calculateStats(throughput);
                const ltStats = calculateStats(latency);
                
                document.getElementById('minThroughput').textContent = tpStats.min;
                document.getElementById('avgThroughput').textContent = tpStats.avg;
                document.getElementById('maxThroughput').textContent = tpStats.max;
                
                document.getElementById('minLatency').textContent = ltStats.min;
                document.getElementById('avgLatency').textContent = ltStats.avg;
                document.getElementById('maxLatency').textContent = ltStats.max;
            }
            
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
    """, 
    slices=slices_data, 
    kpis=kpis_data, 
    activities=activities_data,
    now=datetime.now(),
    timestamps=timestamps_data,
    throughput=throughput_data,
    latency=latency_data
    )

# API Endpoints
@app.route('/api/slices', methods=['GET'])
def get_slices():
    return jsonify(generate_mock_slices())

@app.route('/api/kpis', methods=['GET'])
def get_kpis():
    return jsonify(generate_mock_kpis())

@app.route('/api/activity', methods=['GET'])
def get_activity():
    return jsonify(generate_mock_activity(15))

# JSON filter for templates
@app.template_filter('tojson')
def to_json(value):
    return json.dumps(value)

# This allows the app to be run directly with: python app.py
if __name__ == '__main__':
    app.run(debug=True, port=8050)

# This allows the app to be imported by main.py
app = app
