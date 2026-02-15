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
    1. Validates all vital signs
    2. Stores the reading in database
    3. Updates device's last_seen timestamp
    4. Triggers alert checking
    """
    return services.create_vital_reading(db, vitals)


@router.get("/vitals/{device_id}/latest", response_model=schemas.VitalReadingDetailed)
def get_latest_vitals(device_id: str, db: Session = Depends(get_db)):
    """Get most recent vital signs for a device"""
    vitals = services.get_latest_vitals(db, device_id)
    if not vitals:
        raise HTTPException(status_code=404, detail="No vitals found for device")
    return vitals


@router.get(
    "/vitals/{device_id}/history", response_model=List[schemas.VitalReadingDetailed]
)
def get_vitals_history(
    device_id: str,
    limit: int = Query(default=100, le=1000),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    """Get historical vitals for a device"""
    return services.get_vitals_history(db, device_id, limit, start_date, end_date)


# ==================== ALERT ENDPOINTS ====================


@router.get("/alerts/{device_id}", response_model=List[schemas.AlertResponse])
def get_alerts(
    device_id: str,
    limit: int = Query(default=50, le=200),
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get alerts for a device, optionally filtered by severity"""
    return services.get_alerts(db, device_id, limit, severity)


@router.get("/alerts/{device_id}/critical", response_model=List[schemas.AlertResponse])
def get_critical_alerts(device_id: str, db: Session = Depends(get_db)):
    """Get only critical alerts for a device"""
    return services.get_alerts(db, device_id, limit=20, severity="CRITICAL")


@router.put("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    """Acknowledge an alert"""
    success = services.acknowledge_alert(db, alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "acknowledged"}


# ==================== ANALYTICS ENDPOINTS ====================


@router.get("/analytics/{device_id}/summary")
def get_summary_stats(
    device_id: str,
    period: str = Query(default="daily", pattern="^(daily|weekly|monthly)$"),
    db: Session = Depends(get_db),
):
    """Get summary statistics for different time periods"""
    return services.get_summary_stats(db, device_id, period)


@router.get("/analytics/{device_id}/correlation")
def get_correlation(
    device_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    """Get correlation analysis between vitals"""
    hours_delta = timedelta(hours=hours)
    return correlation_engine.calculate_correlations(db, device_id, hours_delta)


@router.get("/analytics/{device_id}/trends")
def get_trends(
    device_id: str,
    days: int = Query(default=7, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """Get trends in vital signs over time"""
    days_delta = timedelta(days=days)
    return correlation_engine.get_trends(db, device_id, days_delta)


# ==================== CALIBRATION ENDPOINTS ====================


@router.post("/devices/{device_id}/calibrate")
def calibrate_device(
    device_id: str,
    calibration: schemas.CalibrationRequest,
    db: Session = Depends(get_db),
):
    """Set resting HR for temperature estimation calibration"""
    result = services.set_resting_hr(db, device_id, calibration.resting_hr)
    if result["status"] == "device_not_found":
        raise HTTPException(status_code=404, detail="Device not found")
    return {"status": "calibrated", "resting_hr": calibration.resting_hr}


@router.get("/devices/{device_id}/thresholds", response_model=schemas.ThresholdConfig)
def get_thresholds(device_id: str, db: Session = Depends(get_db)):
    """Get alert thresholds for device"""
    thresholds = services.get_thresholds(db, device_id)
    return {"thresholds": thresholds}


@router.post("/devices/{device_id}/thresholds")
def set_thresholds(
    device_id: str,
    thresholds: schemas.ThresholdConfig,
    db: Session = Depends(get_db),
):
    """Update alert thresholds for device"""
    # Check if device exists
    device = services.get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    for threshold_item in thresholds.thresholds:
        # Convert response model back to create/update model if needed or pass directly
        # services.update_threshold expects ThresholdCreate
        update_data = schemas.ThresholdCreate(
            threshold_type=threshold_item.threshold_type,
            threshold_value=threshold_item.threshold_value,
            enabled=threshold_item.enabled,
        )
        services.update_threshold(db, device_id, update_data)

    return {"status": "updated"}


# ==================== STATE CONTROL ENDPOINTS ====================

# Simple in-memory queue for state commands (use Redis in production)
pending_state_commands = {}


@router.post("/devices/{device_id}/state")
def set_device_state(device_id: str, command: schemas.StateCommand):
    """
    Queue a state change command for the device.
    Device polls this on next cloud sync to update state.
    """
    if command.state not in ["idle", "monitoring", "paused"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid state. Must be 'idle', 'monitoring', or 'paused'",
        )

    if device_id not in pending_state_commands:
        pending_state_commands[device_id] = []

    pending_state_commands[device_id].append(command.state)
    return {"status": "queued", "state": command.state}


@router.get("/devices/{device_id}/state/pending")
def get_pending_state(device_id: str):
    """
    Get and clear pending state commands for device.
    Device polls this endpoint.
    """
    if device_id in pending_state_commands and pending_state_commands[device_id]:
        state = pending_state_commands[device_id][-1]  # Get most recent
        pending_state_commands[device_id] = []  # Clear queue
        return {"has_pending": True, "state": state}
    return {"has_pending": False}


# ==================== DATA MANAGEMENT ====================


@router.delete("/devices/{device_id}/data")
def clear_device_data(device_id: str, db: Session = Depends(get_db)):
    """
    Clear all vitals and alerts for a device.
    Useful for resetting data while keeping device registration.
    """
    device = services.get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Delete all vitals
    vitals_deleted = services.delete_device_vitals(db, device_id)

    # Delete all alerts
    alerts_deleted = services.delete_device_alerts(db, device_id)

    return {
        "device_id": device_id,
        "vitals_deleted": vitals_deleted,
        "alerts_deleted": alerts_deleted,
        "message": f"Cleared {vitals_deleted} vitals and {alerts_deleted} alerts",
    }
