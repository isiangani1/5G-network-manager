"""
Dashboard configuration settings.
"""
import os
from typing import Dict, Any

# API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Default slice configuration
DEFAULT_SLICE_CONFIG = {
    'slice1': {
        'name': 'eMBB', 
        'color': '#636EFA', 
        'priority': 1, 
        'quota': 40, 
        'description': 'Enhanced Mobile Broadband',
        'icon': 'wifi'
    },
    'slice2': {
        'name': 'URLLC', 
        'color': '#EF553B', 
        'priority': 2, 
        'quota': 30, 
        'description': 'Ultra-Reliable Low Latency',
        'icon': 'bolt'
    },
    'slice3': {
        'name': 'mMTC', 
        'color': '#00CC96', 
        'priority': 3, 
        'quota': 30, 
        'description': 'Massive Machine Type Comm',
        'icon': 'microchip'
    }
}

# Dashboard settings
DASHBOARD_CONFIG = {
    'refresh_interval': 30000,  # 30 seconds
    'max_alerts': 5,
    'default_time_range': '1h'  # 1 hour
}

# Chart configurations
CHART_CONFIG = {
    'performance': {
        'height': 400,
        'margin': {'t': 30, 'l': 10, 'r': 10, 'b': 10},
        'legend': {
            'orientation': 'h',
            'yanchor': 'bottom',
            'y': 1.02,
            'xanchor': 'right',
            'x': 1
        },
        'yaxis': {
            'title': 'Latency (ms)',
            'side': 'left'
        },
        'yaxis2': {
            'title': 'Throughput (Mbps)',
            'side': 'right',
            'overlaying': 'y'
        }
    },
    'resource': {
        'height': 300,
        'margin': {'t': 30, 'l': 10, 'r': 10, 'b': 30},
        'xaxis': {'title': 'Slice'},
        'yaxis': {'title': 'Quota Used (%)'}
    }
}

# Alert severity levels
ALERT_SEVERITY = {
    'critical': {
        'color': 'danger',
        'icon': 'exclamation-triangle'
    },
    'warning': {
        'color': 'warning',
        'icon': 'exclamation-circle'
    },
    'info': {
        'color': 'info',
        'icon': 'info-circle'
    },
    'success': {
        'color': 'success',
        'icon': 'check-circle'
    }
}
