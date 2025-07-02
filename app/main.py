from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.wsgi import WSGIMiddleware
import uvicorn
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Import the Flask app from the dashboard module
from app.dashboard.app import app as flask_app

# Create FastAPI app
app = FastAPI(title="5G Network Slice Manager")

# Mount the Flask app at the root URL
app.mount("/", WSGIMiddleware(flask_app))

# Redirect /dashboard to /dashboard/ to handle the trailing slash
@app.get("/dashboard")
async def redirect_dashboard():
    return RedirectResponse(url="/")

if __name__ == "__main__":
    # Create static directory if it doesn't exist
    import os
    os.makedirs("static", exist_ok=True)
    
    # Run the FastAPI app with Uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8050,
        reload=True,
        log_level="info"
    )
