from datetime import datetime

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .audit import run_energy_audit
from .models import EnergyAuditLog, EnergyDevice, EnergySensorReading

router = APIRouter(prefix="/energy", tags=["Energy"])


# --- Pydantic Models ---
class DeviceCreate(BaseModel):
    device_id: str
    device_name: str
    location: str


class ReadingCreate(BaseModel):
    device_id: str
    timestamp: datetime = None
    sensor_1: dict
    sensor_2: dict
    environment: dict


# --- Device Endpoints ---
@router.post("/devices")
def register_device(device: DeviceCreate, db: Session = Depends(get_db)):
    db_device = (
        db
        .query(EnergyDevice)
        .filter(EnergyDevice.device_id == device.device_id)
        .first()
    )
    if db_device:
        raise HTTPException(status_code=400, detail="Device already registered")

    new_device = EnergyDevice(
        device_id=device.device_id,
        device_name=device.device_name,
        location=device.location,
        last_seen=datetime.utcnow(),
    )
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    return new_device


@router.get("/devices")
def get_devices(db: Session = Depends(get_db)):
    return db.query(EnergyDevice).all()


@router.get("/devices/{device_id}")
def get_device(device_id: str, db: Session = Depends(get_db)):
    device = db.query(EnergyDevice).filter(EnergyDevice.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


# --- Readings Endpoint ---
@router.post("/readings")
def post_reading(reading: ReadingCreate, db: Session = Depends(get_db)):
    # 1. Update Device Last Seen
    device = (
        db
        .query(EnergyDevice)
        .filter(EnergyDevice.device_id == reading.device_id)
        .first()
    )
    if not device:
        # Auto-register if not exists (optional, but good for IoT)
        device = EnergyDevice(
            device_id=reading.device_id, device_name="New Device", location="Unknown"
        )
        db.add(device)

    device.last_seen = datetime.utcnow()

    # 2. Save Reading
    new_reading = EnergySensorReading(
        device_id=reading.device_id,
        timestamp=datetime.utcnow(),
        sensor_1_amps=reading.sensor_1.get("current_amps", 0),
        sensor_1_watts=reading.sensor_1.get("watts", 0),
        sensor_2_amps=reading.sensor_2.get("current_amps", 0),
        sensor_2_watts=reading.sensor_2.get("watts", 0),
        temperature_c=reading.environment.get("temperature_c", 0),
        humidity_percent=reading.environment.get("humidity_percent", 0),
        light_raw=reading.environment.get("light_raw", 0),
        light_lux=reading.environment.get("light_lux", 0),
    )
    db.add(new_reading)
    db.commit()

    # 3. Trigger Audit
    alerts = run_energy_audit(db, reading.device_id)

    return {"status": "success", "alerts_generated": len(alerts)}


@router.get("/readings/{device_id}")
def get_latest_readings(
    device_id: str, limit: int = 100, db: Session = Depends(get_db)
):
    return (
        db
        .query(EnergySensorReading)
        .filter(EnergySensorReading.device_id == device_id)
        .order_by(EnergySensorReading.timestamp.desc())
        .limit(limit)
        .all()
    )


# --- Audit Endpoints ---
@router.get("/audit/{device_id}/alerts")
def get_alerts(device_id: str, limit: int = 50, db: Session = Depends(get_db)):
    return (
        db
        .query(EnergyAuditLog)
        .filter(EnergyAuditLog.device_id == device_id)
        .order_by(EnergyAuditLog.timestamp.desc())
        .limit(limit)
        .all()
    )
