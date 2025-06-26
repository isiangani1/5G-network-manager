"""
API package for the 5G Slice Manager application.

This package contains all the API endpoints and routes for the application.
"""

from fastapi import APIRouter

from app.api.routers import (
    auth,
    users,
    slices,
    devices,
    metrics,
    dashboard
)

api_router = APIRouter(prefix="/api/v1")

# Include all API routes
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["auth"]
)

api_router.include_router(
    users.router,
    prefix="/users",
    tags=["users"]
)

api_router.include_router(
    slices.router,
    prefix="/slices",
    tags=["slices"]
)

api_router.include_router(
    devices.router,
    prefix="/devices",
    tags=["devices"]
)

api_router.include_router(
    metrics.router,
    prefix="/metrics",
    tags=["metrics"]
)

api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["dashboard"]
)

# Include dashboard routes if needed
# api_router.include_router(
#     dashboard.router,
#     prefix="/dashboard",
#     tags=["dashboard"]
# )

# This makes the router available when importing from app.api
__all__ = ['api_router']
