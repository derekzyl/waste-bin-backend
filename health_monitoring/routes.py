"""
Health Monitoring API Routes
All routes under /health/ prefix for multi-project coexistence
"""

from datetime import datetime, timedelta
from typing import List, Optional

from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from . import correlation_engine, schemas, services

router = APIRouter(prefix="/health", tags=["Health Monitoring"])


# ==================== DEVICE ENDPOINTS ====================


@router.post("/devices", response_model=schemas.DeviceResponse)
def register_device(device: schemas.DeviceCreate, db: Session = Depends(get_db)):
    """Register new health monitoring device"""
    return services.create_device(db, device)


@router.get("/devices", response_model=List[schemas.DeviceResponse])
def list_devices(db: Session = Depends(get_db)):
    """List all health monitoring devices"""
    return services.get_all_devices(db)


@router.get("/devices/{device_id}", response_model=schemas.DeviceResponse)
def get_device(device_id: str, db: Session = Depends(get_db)):
    """Get device details"""
    device = services.get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


# ==================== VITALS ENDPOINTS ====================


@router.post("/vitals", response_model=schemas.VitalReadingResponse)
def receive_vitals(vitals: schemas.VitalReadingCreate, db: Session = Depends(get_db)):
    """
    PRIMARY ENDPOINT - Receive vitals from ESP32 (HR + SpO2 + Temp)

    This endpoint:
    1. Stores the vital signs reading
    2. Runs the correlation engine to detect patterns
    3. Generates alerts for critical conditions
    4. Updates device last_seen timestamp
    """
    # Store vitals
    reading = services.store_vitals(db, vitals)

    # Run correlation engine
    alerts = correlation_engine.analyze_vitals(db, vitals)

    # Update last seen
    services.update_last_seen(db, vitals.device_id)

    # Filter critical alerts
    critical_alerts = [
        {"type": a.alert_type, "severity": a.severity, "message": a.message}
        for a in alerts
        if a.severity == "CRITICAL"
    ]

    return {
        "status": "success",
        "reading_id": reading.id,
        "alerts_generated": len(alerts),
        "critical_alerts": critical_alerts,
    }


@router.get("/vitals/{device_id}/latest", response_model=schemas.VitalReadingDetailed)
def get_latest_vitals(device_id: str, db: Session = Depends(get_db)):
    """Get most recent reading"""
    reading = services.get_latest_reading(db, device_id)
    if not reading:
        raise HTTPException(status_code=404, detail="No readings found")
    return reading


@router.get(
    "/vitals/{device_id}/history", response_model=List[schemas.VitalReadingDetailed]
)
def get_history(
    device_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db),
):
    """Get historical readings"""
    if not start_date:
        start_date = datetime.utcnow() - timedelta(days=7)
    if not end_date:
        end_date = datetime.utcnow()
    return services.get_readings_range(db, device_id, start_date, end_date, limit)


# ==================== ANALYTICS ENDPOINTS ====================


@router.get("/analytics/{device_id}/summary")
def get_summary(
    device_id: str,
    period: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    db: Session = Depends(get_db),
):
    """Get summary statistics"""
    return correlation_engine.get_summary_stats(db, device_id, period)


@router.get("/analytics/{device_id}/correlation")
def get_correlation(device_id: str, hours: int = 24, db: Session = Depends(get_db)):
    """Analyze HR vs SpO2 vs Temperature correlation"""
    return correlation_engine.analyze_health_patterns(db, device_id, hours)


# ==================== ALERT ENDPOINTS ====================


@router.get("/alerts/{device_id}", response_model=List[schemas.AlertResponse])
def get_alerts(device_id: str, db: Session = Depends(get_db)):
    """Get all alerts"""
    return services.get_device_alerts(db, device_id)


@router.get("/alerts/{device_id}/critical", response_model=List[schemas.AlertResponse])
def get_critical_alerts(device_id: str, db: Session = Depends(get_db)):
    """Get only critical alerts (SpO2 < 90, severe conditions)"""
    return services.get_critical_alerts(db, device_id)


@router.put("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    """Mark alert as seen"""
    result = services.acknowledge_alert(db, alert_id)
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Alert not found")
    return result


# ==================== CALIBRATION ENDPOINTS ====================


@router.post("/devices/{device_id}/calibrate")
def calibrate_resting_hr(
    device_id: str,
    calibration: schemas.RestingHRCalibration,
    db: Session = Depends(get_db),
):
    """Set resting heart rate for temperature estimation"""
    result = services.set_resting_hr(db, device_id, calibration.resting_hr)
    if result["status"] == "device_not_found":
        raise HTTPException(status_code=404, detail="Device not found")
    return result


# ==================== THRESHOLD ENDPOINTS ====================


@router.get("/thresholds/{device_id}", response_model=List[schemas.ThresholdResponse])
def get_thresholds(device_id: str, db: Session = Depends(get_db)):
    """Get alert thresholds for device"""
    return services.get_thresholds(db, device_id)


@router.post("/thresholds/{device_id}", response_model=schemas.ThresholdResponse)
def update_threshold(
    device_id: str, threshold: schemas.ThresholdCreate, db: Session = Depends(get_db)
):
    """Update or create alert threshold"""
    return services.update_threshold(db, device_id, threshold)
