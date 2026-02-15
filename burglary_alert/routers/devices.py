"""Devices router."""

from datetime import datetime
from typing import List, Optional

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..models.device_status import DeviceStatus
from ..utils.auth import verify_device_api_key

router = APIRouter(prefix="/device", tags=["Devices"])


class HeartbeatRequest(BaseModel):
    """Heartbeat request model."""

    device_id: str
    status: str = "online"
    ip_address: Optional[str] = None
    firmware_version: Optional[str] = None


class DeviceResponse(BaseModel):
    """Device response model."""

    device_id: str
    status: str
    ip_address: Optional[str]
    last_heartbeat: Optional[str]
    firmware_version: Optional[str]


@router.post("/heartbeat")
async def receive_heartbeat(
    data: HeartbeatRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_device_api_key),
):
    """
    Receive heartbeat from device.
    """
    try:
        device = (
            db
            .query(DeviceStatus)
            .filter(DeviceStatus.device_id == data.device_id)
            .first()
        )

        if not device:
            device = DeviceStatus(device_id=data.device_id)
            db.add(device)

        device.status = data.status
        device.last_heartbeat = datetime.utcnow()
        if data.ip_address:
            device.ip_address = data.ip_address
        if data.firmware_version:
            device.firmware_version = data.firmware_version

        db.commit()
        db.refresh(device)

        return {"status": "success", "message": "Heartbeat received"}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Error processing heartbeat: {str(e)}"
        )


@router.get("/status", response_model=List[DeviceResponse])
async def get_all_devices(db: Session = Depends(get_db)):
    """
    Get status of all devices.
    """
    devices = db.query(DeviceStatus).all()

    # Check for stale devices (offline if no heartbeat > 5 min)
    # This logic handles display; actual DB update could come from a scheduled task
    # For now, we return what's in DB, but client can calculate staleness

    return [device.to_dict() for device in devices]
