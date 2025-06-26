"""
Database package for the application.

This package contains database configuration, models, and utilities.
"""

from .database import (
    Base,
    get_db,
    get_sync_db,
    async_session_factory,
    SessionLocal,
    async_engine,
    sync_engine,
    init_db,
)

# Alias for backward compatibility
AsyncSessionLocal = async_session_factory

# Import models to ensure they are registered with SQLAlchemy
from . import models  # noqa: F401

__all__ = [
    'Base',
    'get_db',
    'get_sync_db',
    'AsyncSessionLocal',
    'SessionLocal',
    'async_engine',
    'sync_engine',
    'init_db',
    'models',
]
