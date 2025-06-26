from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(
    prefix="/devices",
    tags=["Devices"],
    responses={404: {"description": "Not found"}},
)

@router.get("/")
async def list_devices():
    """List all devices"""
    return [
        {"id": "device1", "name": "UE-1", "type": "user_equipment", "status": "connected"},
        {"id": "device2", "name": "gNB-1", "type": "base_station", "status": "connected"},
        {"id": "device3", "name": "UPF-1", "type": "user_plane", "status": "connected"}
    ]

@router.get("/{device_id}")
async def get_device(device_id: str):
    """Get device details"""
    return {"id": device_id, "name": f"Device {device_id}", "status": "active"}

@router.get("/{device_id}/metrics")
async def get_device_metrics(device_id: str):
    """Get device metrics"""
    return {"device_id": device_id, "metrics": {}}
