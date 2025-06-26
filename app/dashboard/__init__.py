"""
5G Slice Manager Dashboard Package

This package contains the FastAPI routes and templates for the 5G Slice Manager dashboard.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

# Import the router from router.py
from .router import router as dashboard_router

# This makes the router available when importing from app.dashboard
__all__ = ['dashboard_router']


if __name__ == '__main__':
    app.run(debug=True, port=8050)
