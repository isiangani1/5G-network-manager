"""
Main API router that includes all the endpoint routers.
"""
from fastapi import APIRouter

from app.api.routers import (
    auth as auth_router,
    dashboard as dashboard_router,
    devices as devices_router,
    metrics as metrics_router,
    slices as slices_router,
    users as users_router
)

# Create main API router
router = APIRouter()

# Include all routers
router.include_router(auth_router.router, prefix="/auth", tags=["Authentication"])
router.include_router(users_router.router, prefix="/users", tags=["Users"])
router.include_router(slices_router.router, prefix="/slices", tags=["Slices"])
router.include_router(devices_router.router, prefix="/devices", tags=["Devices"])
router.include_router(metrics_router.router, prefix="/metrics", tags=["Metrics"])
router.include_router(dashboard_router.router, prefix="/dashboard", tags=["Dashboard"])
