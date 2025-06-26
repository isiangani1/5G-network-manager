"""
Database configuration and session management for the application.
"""

import logging
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import sessionmaker, Session as SyncSession
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Parse database URL
try:
    # Use the async URL for async operations
    db_url = settings.DATABASE_URL_ASYNC
    sync_db_url = settings.DATABASE_URL_SYNC
    
    url = make_url(db_url)
    logger.info(f"Initializing database connection to: {url.host}:{url.port}/{url.database}")
    
    # Configure database engines
    if url.drivername.startswith("sqlite"):
        # SQLite configuration (for testing)
        async_engine = create_async_engine(
            db_url.replace("sqlite:///", "sqlite+aiosqlite:///"),
            connect_args={"check_same_thread": False},
            echo=settings.DEBUG,
            future=True,
            pool_pre_ping=True
        )
        sync_engine = create_engine(
            sync_db_url,
            connect_args={"check_same_thread": False},
            echo=settings.DEBUG,
            future=True,
            pool_pre_ping=True
        )
    else:
        # PostgreSQL/other database configuration
        async_engine = create_async_engine(
            db_url,
            echo=settings.DEBUG,
            future=True,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            connect_args={
                'server_settings': {
                    'application_name': '5g_slice_manager',
                    'timezone': 'UTC'
                }
            }
        )
        sync_engine = create_engine(
            settings.DATABASE_URL.replace("+asyncpg", ""),
            echo=settings.DEBUG,
            future=True,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800
        )

except Exception as e:
    logger.error(f"Error configuring database: {e}")
    raise

# Create async session factory with connection pool settings
async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
    future=True
)

# Create sync session factory
SessionLocal = sessionmaker(
    bind=sync_engine,
    class_=SyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

# Base class for models
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

# Async database session dependency
@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides an async database session with robust error handling.
    
    Yields:
        AsyncSession: An async database session
        
    Raises:
        SQLAlchemyError: If there's an error creating or using the session
        
    Example:
        ```python
        async with get_db() as db:
            result = await db.execute(select(User))
            users = result.scalars().all()
        ```
    """
    session = None
    try:
        # Create a new session
        session = async_session_factory()
        
        # Test the connection
        await session.connection()
        
        # Yield the session to the caller
        yield session
        
        # Commit the transaction if no exceptions occurred
        await session.commit()
        
    except SQLAlchemyError as e:
        # Log the error and roll back the transaction
        logger.error(f"Database error: {e}")
        if session:
            await session.rollback()
        raise
        
    except Exception as e:
        # Log any other exceptions
        logger.error(f"Unexpected error in database session: {e}")
        if session:
            await session.rollback()
        raise
        
    finally:
        # Always close the session
        if session:
            try:
                await session.close()
            except Exception as e:
                logger.error(f"Error closing database session: {e}")
        await session.close()

# Sync database session (for migrations, etc.)
@asynccontextmanager
async def get_sync_db() -> AsyncGenerator[SyncSession, None]:
    """
    Dependency that provides a synchronous database session.
    
    Yields:
        Session: A synchronous database session
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        session.close()

# Database initialization
async def init_db() -> None:
    """
    Initialize the database by creating all tables if they don't exist.
    """
    from app.db import models  # Import models to ensure they're registered with SQLAlchemy
    
    try:
        async with async_engine.begin() as conn:
            # Create all tables with a checkfirst=True parameter to avoid errors if tables exist
            await conn.run_sync(
                lambda conn: Base.metadata.create_all(bind=conn, checkfirst=True)
            )
            logger.info("Database tables verified/created successfully")
            
        # Create default admin user if it doesn't exist
        async with AsyncSessionLocal() as db:
            from app.db.models import User
            from app.core.security import get_password_hash
            
            try:
                admin = await db.execute(
                    select(User).where(User.username == "admin")
                )
                admin = admin.scalar_one_or_none()
                
                if not admin:
                    admin = User(
                        username="admin",
                        email="admin@example.com",
                        full_name="Administrator",
                        hashed_password=get_password_hash("admin"),
                        is_active=True,
                        is_superuser=True
                    )
                    db.add(admin)
                    await db.commit()
                    logger.info("Default admin user created")
            except Exception as user_error:
                await db.rollback()
                logger.warning(f"Could not create admin user: {user_error}")
                
    except Exception as e:
        # Log the error but don't crash - the app might still work with existing tables
        logger.warning(f"Database initialization warning: {e}")
        logger.info("Attempting to continue with existing database schema...")
