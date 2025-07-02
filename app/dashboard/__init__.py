"""
5G Slice Manager Dashboard Package

This package contains the Flask application for the 5G Slice Manager dashboard.
"""

# Import the Flask app from app.py
from .app import app as flask_app

# Make the Flask app available when importing from app.dashboard
__all__ = ['flask_app']
