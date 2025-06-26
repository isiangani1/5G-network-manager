"""Routers package for the API endpoints."""
from fastapi import APIRouter

from .auth import router as auth_router
from .users import router as users_router
from .slices import router as slices_router
from .devices import router as devices_router
from .metrics import router as metrics_router
from .ns3 import router as ns3_router

# Create main router
router = APIRouter()

# Include all routers
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(users_router, prefix="/users", tags=["users"])
router.include_router(slices_router, prefix="/slices", tags=["slices"])
router.include_router(devices_router, prefix="/devices", tags=["devices"])
router.include_router(metrics_router, prefix="/metrics", tags=["metrics"])
router.include_router(ns3_router, prefix="/ns3", tags=["ns3"])

# Export all routers for easy importing
__all__ = [
    "router",
    "auth_router",
    "users_router",
    "slices_router",
    "devices_router",
    "metrics_router",
    "ns3_router",
]
