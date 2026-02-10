from datetime import datetime

import httpx
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .audit import run_energy_audit
from .models import EnergyAuditLog, EnergyDevice, EnergyGoal, EnergySensorReading

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


class GoalCreate(BaseModel):
    device_id: str
    target_kwh: float
    period_start: datetime
    period_end: datetime


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


# --- Goal Endpoints ---
@router.post("/goals")
def set_goal(goal: GoalCreate, db: Session = Depends(get_db)):
    # Deactivate existing goals for same period (simplification)
    db.query(EnergyGoal).filter(
        EnergyGoal.device_id == goal.device_id,
        EnergyGoal.period_end > datetime.utcnow(),
    ).delete()

    new_goal = EnergyGoal(
        device_id=goal.device_id,
        target_kwh=goal.target_kwh,
        period_start=goal.period_start,
        period_end=goal.period_end,
    )
    db.add(new_goal)
    db.commit()
    return {"status": "success", "goal_id": new_goal.id}


@router.get("/goals/progress/{device_id}")
def get_goal_progress(device_id: str, db: Session = Depends(get_db)):
    # Find active goal
    now = datetime.utcnow()
    goal = (
        db
        .query(EnergyGoal)
        .filter(
            EnergyGoal.device_id == device_id,
            EnergyGoal.period_start <= now,
            EnergyGoal.period_end >= now,
        )
        .first()
    )

    if not goal:
        return {"has_goal": False, "consumed": 0, "target": 0}

    # Calculate sum of watts * time (simplified approximation)
    # Ideally we'd integrate power over time. For MVP, we'll just sum watts and assume 5s intervals.
    # Total kWh = (Sum(Watts) * 5s) / (3600 * 1000)

    readings = (
        db
        .query(EnergySensorReading)
        .filter(
            EnergySensorReading.device_id == device_id,
            EnergySensorReading.timestamp >= goal.period_start,
            EnergySensorReading.timestamp <= now,
        )
        .all()
    )

    total_watts_accumulated = sum(
        (r.sensor_1_watts or 0) + (r.sensor_2_watts or 0) for r in readings
    )
    consumed_kwh = (total_watts_accumulated * 5) / (3600 * 1000)

    return {
        "has_goal": True,
        "consumed_kwh": round(consumed_kwh, 3),
        "target_kwh": goal.target_kwh,
        "percentage": round((consumed_kwh / goal.target_kwh) * 100, 1),
    }


# --- Caching for Weather ---
weather_cache = {
    "data": None,
    "timestamp": None,
    "location": "default",  # Can expand to cache per location if needed
}


# --- Readings Endpoint ---
@router.post("/readings")
async def post_reading(reading: ReadingCreate, db: Session = Depends(get_db)):
    # 1. Update Device Last Seen
    device = (
        db
        .query(EnergyDevice)
        .filter(EnergyDevice.device_id == reading.device_id)
        .first()
    )
    if not device:
        # Auto-register if not exists
        device = EnergyDevice(
            device_id=reading.device_id, device_name="New Device", location="Unknown"
        )
        db.add(device)

    device.last_seen = datetime.utcnow()

    # 2. Save Reading with Weather Data
    outdoor_temp = None

    # Check cache first (Cache for 15 minutes)
    use_cache = False
    if weather_cache["data"] is not None and weather_cache["timestamp"] is not None:
        if (
            datetime.utcnow() - weather_cache["timestamp"]
        ).total_seconds() < 900:  # 15 mins
            outdoor_temp = weather_cache["data"]
            use_cache = True

    if not use_cache:
        try:
            # Async HTTP request with timeout
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(
                    "https://api.open-meteo.com/v1/forecast?latitude=6.7432&longitude=6.1385&current=temperature_2m"
                )
                if r.status_code == 200:
                    outdoor_temp = r.json()["current"]["temperature_2m"]
                    # Update cache
                    weather_cache["data"] = outdoor_temp
                    weather_cache["timestamp"] = datetime.utcnow()
        except Exception as e:
            # If fetch fails, use cached value if available (even if expired) as backup
            outdoor_temp = weather_cache.get("data")
            print(f"Weather fetch error: {e}")

    new_reading = EnergySensorReading(
        device_id=reading.device_id,
        timestamp=datetime.utcnow(),
        sensor_1_amps=reading.sensor_1.get("current_amps", 0),
        sensor_1_watts=reading.sensor_1.get("watts", 0),
        sensor_1_voltage=reading.sensor_1.get("voltage", 220.0),
        sensor_2_amps=reading.sensor_2.get("current_amps", 0),
        sensor_2_watts=reading.sensor_2.get("watts", 0),
        sensor_2_voltage=reading.sensor_2.get("voltage", 220.0),
        temperature_c=reading.environment.get("temperature_c", 0),
        humidity_percent=reading.environment.get("humidity_percent", 0),
        light_raw=reading.environment.get("light_raw", 0),
        light_lux=reading.environment.get("light_lux", 0),
        outdoor_temp_c=outdoor_temp,
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
