"""
Dashboard router for serving the main dashboard and related pages.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

# Set up templates directory
BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()

@router.get("", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Serve the main dashboard page."""
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "title": "5G Slice Manager - Dashboard"}
    )

@router.get("/slices", response_class=HTMLResponse)
async def slices_page(request: Request):
    """Serve the slices management page."""
    return templates.TemplateResponse(
        "slices.html",
        {"request": request, "title": "5G Slice Manager - Slices"}
    )

@router.get("/devices", response_class=HTMLResponse)
async def devices_page(request: Request):
    """Serve the devices management page."""
    return templates.TemplateResponse(
        "devices.html",
        {"request": request, "title": "5G Slice Manager - Devices"}
    )

@router.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    """Serve the analytics page."""
    return templates.TemplateResponse(
        "analytics.html",
        {"request": request, "title": "5G Slice Manager - Analytics"}
    )

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Serve the settings page."""
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "title": "5G Slice Manager - Settings"}
    )
