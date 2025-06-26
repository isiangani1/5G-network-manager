#!/usr/bin/env python3
"""
Main entry point for the 5G Slice Manager application.
Handles database initialization and starts the FastAPI server.
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict
from fastapi.middleware.wsgi import WSGIMiddleware

# Configure basic logging first
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add the project root to the Python path
project_root = str(Path(__file__).parent.resolve())
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import after path setup
try:
    from app.core.config import settings
    
    # Reconfigure logging with settings from config
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger.info(f"Logging configured with level: {settings.LOG_LEVEL}")
    
    # Try to import Flask app
    try:
        from app.dashboard.app import app as flask_app
        from werkzeug.middleware.proxy_fix import ProxyFix
        flask_app.wsgi_app = ProxyFix(flask_app.wsgi_app, x_proto=1, x_host=1)
        logger.info("Flask app imported successfully")
    except ImportError as e:
        logger.warning(f"Could not import Flask app: {e}")
        flask_app = None
    
    # Import database and API components
    from app.db.database import init_db, async_engine, Base, get_db
    from app.db.models import User
    from app.api import api_router
    
    # FastAPI imports
    import uvicorn
    from fastapi import FastAPI, Depends, HTTPException, status
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.wsgi import WSGIMiddleware
    from fastapi.openapi.docs import get_swagger_ui_html
    from fastapi.openapi.utils import get_openapi
    from fastapi.responses import JSONResponse
    from fastapi.staticfiles import StaticFiles
    
except Exception as e:
    logger.error(f"Failed to initialize application: {e}")
    raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown events."""
    # Initialize database on startup
    try:
        logger.info("Initializing database...")
        await init_db()
        logger.info("Database initialization completed")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise
    
    yield
    
    # Clean up resources on shutdown
    await async_engine.dispose()

def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        description="5G Network Slice Manager API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan
    )
    
    # Mount Flask app if available
    if flask_app is not None:
        # Mount the Flask app without any static file configuration
        app.mount("/", WSGIMiddleware(flask_app))
        logger.info("Mounted Flask dashboard at /dashboard")
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routes
    app.include_router(api_router, prefix="/api/v1")
    
    # Root endpoint redirects to dashboard
    @app.get("/")
    async def root() -> Dict[str, Any]:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/dashboard")
    
    # Custom docs endpoints
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url="/api/openapi.json",
            title=f"{settings.APP_NAME} - Swagger UI",
            oauth2_redirect_url=None,
            swagger_js_url="/static/swagger-ui-bundle.js",
            swagger_css_url="/static/swagger-ui.css",
        )
    
    # Health check endpoint
    @app.get("/health", status_code=status.HTTP_200_OK)
    async def health_check() -> Dict[str, str]:
        return {"status": "ok"}
    
    # Root endpoint
    @app.get("/")
    async def root() -> Dict[str, Any]:
        return {
            "name": settings.APP_NAME,
            "version": "0.1.0",
            "docs": "/docs",
            "openapi": f"{settings.API_V1_STR}/openapi.json"
        }
    
    return app

# Create the application
app = create_application()

def run():
    """Run the FastAPI application using Uvicorn."""
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        workers=settings.WEB_CONCURRENCY,
    )

if __name__ == "__main__":
    run()
