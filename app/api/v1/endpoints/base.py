from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/")
async def root():
    return {
        "message": "Welcome to the 5G Slicing API",
        "status": "operational",
        "version": "1.0.0"
    }

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
