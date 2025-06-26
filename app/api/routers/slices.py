from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(
    prefix="/slices",
    tags=["Slices"],
    responses={404: {"description": "Not found"}},
)

@router.get("/")
async def list_slices():
    """List all network slices"""
    return [{"id": "slice1", "name": "eMBB"}, 
            {"id": "slice2", "name": "URLLC"}, 
            {"id": "slice3", "name": "mMTC"}]

@router.get("/{slice_id}")
async def get_slice(slice_id: str):
    """Get slice details"""
    return {"id": slice_id, "name": f"Slice {slice_id}", "status": "active"}

@router.post("/{slice_id}")
async def update_slice(slice_id: str, config: dict):
    """Update slice configuration"""
    return {"id": slice_id, "status": "updated", "config": config}
