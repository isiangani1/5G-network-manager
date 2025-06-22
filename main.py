from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.responses import RedirectResponse
import uvicorn

# Import the Flask app from app.py
from app import app as flask_app

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
