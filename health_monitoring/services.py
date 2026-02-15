"""
Health Monitoring Business Logic Services
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from . import models, schemas


def create_device(db: Session, device: schemas.DeviceCreate) -> models.HealthDevice:
    """Register a new health monitoring device"""
    db_device = (
        db
        .query(models.HealthDevice)
        .filter(models.HealthDevice.device_id == device.device_id)
        .first()
    )

    if db_device:
        # Update existing device
        db_device.device_name = device.device_name or db_device.device_name
        db_device.user_name = device.user_name or db_device.user_name
        db_device.date_of_birth = device.date_of_birth or db_device.date_of_birth
        db_device.gender = device.gender or db_device.gender
        db_device.resting_hr = device.resting_hr
        db_device.is_athlete = device.is_athlete
        db_device.last_seen = datetime.utcnow()
    else:
        # Create new device
        db_device = models.HealthDevice(
            device_id=device.device_id,
            device_name=device.device_name,
            user_name=device.user_name,
            date_of_birth=device.date_of_birth,
            gender=device.gender,
            resting_hr=device.resting_hr,
            is_athlete=device.is_athlete,
            last_seen=datetime.utcnow(),
        )
        db.add(db_device)

        # Create default thresholds
        default_thresholds = [
            {"type": "HR_HIGH", "value": 100.0},
            {"type": "HR_LOW", "value": 50.0},
            {"type": "SPO2_LOW", "value": 95.0},
            {"type": "SPO2_CRITICAL", "value": 90.0},
            {"type": "TEMP_HIGH", "value": 38.0},
            {"type": "TEMP_LOW", "value": 35.5},
        ]

        for threshold in default_thresholds:
            db_threshold = models.HealthThreshold(
                device_id=device.device_id,
                threshold_type=threshold["type"],
                threshold_value=threshold["value"],
                enabled=True,
            )
            db.add(db_threshold)

    db.commit()
    db.refresh(db_device)
    return db_device


def get_all_devices(db: Session) -> List[models.HealthDevice]:
    """Get all registered devices"""
    return db.query(models.HealthDevice).all()


def get_device(db: Session, device_id: str) -> Optional[models.HealthDevice]:
    """Get device by ID"""
    return (
        db
        .query(models.HealthDevice)
        .filter(models.HealthDevice.device_id == device_id)
        .first()
    )


def create_vital_reading(
    db: Session, vitals: schemas.VitalReadingCreate
) -> schemas.VitalReadingResponse:
    """Store reading, run analysis, and return summary"""
    # 1. Ensure device exists and update last seen
    device = get_device(db, vitals.device_id)
    if not device:
        create_device(db, schemas.DeviceCreate(device_id=vitals.device_id))

    update_last_seen(db, vitals.device_id)

    # 2. Store the reading
    reading = models.HealthVitalReading(
        device_id=vitals.device_id,
        timestamp=datetime.fromtimestamp(vitals.timestamp),
        heart_rate=vitals.vitals.heart_rate.bpm,
        hr_signal_quality=vitals.vitals.heart_rate.signal_quality,
        is_hr_valid=vitals.vitals.heart_rate.is_valid,
        spo2=vitals.vitals.spo2.percent,
        spo2_signal_quality=vitals.vitals.spo2.signal_quality,
        is_spo2_valid=vitals.vitals.spo2.is_valid,
        temperature=vitals.vitals.temperature.celsius,
        temp_source=vitals.vitals.temperature.source,
        is_temp_estimated=vitals.vitals.temperature.is_estimated,
        battery_percent=vitals.system.battery_percent,
        battery_voltage=vitals.system.battery_voltage,
        wifi_rssi=vitals.system.wifi_rssi,
        uptime_seconds=vitals.system.uptime_seconds,
    )

    db.add(reading)
    db.commit()
    db.refresh(reading)

    # 3. specific imports to avoid circular dependency
    from . import correlation_engine

    # 4. Analyze for alerts
    generated_alerts = correlation_engine.analyze_vitals(db, vitals)

    critical_alerts = [
        {
            "id": a.id,
            "type": a.alert_type,
            "message": a.message,
            "timestamp": a.timestamp,
        }
        for a in generated_alerts
        if a.severity == "CRITICAL"
    ]

    # 5. Return summary response
    return {
        "status": "success",
        "reading_id": reading.id,
        "alerts_generated": len(generated_alerts),
        "critical_alerts": critical_alerts,
    }


def update_last_seen(db: Session, device_id: str):
    """Update device last seen timestamp"""
    device = get_device(db, device_id)
    if device:
        device.last_seen = datetime.utcnow()
        db.commit()


def get_latest_vitals(
    db: Session, device_id: str
) -> Optional[models.HealthVitalReading]:
    """Get most recent vital reading"""
    return (
        db
        .query(models.HealthVitalReading)
        .filter(models.HealthVitalReading.device_id == device_id)
        .order_by(models.HealthVitalReading.timestamp.desc())
        .first()
    )


def get_vitals_history(
    db: Session,
    device_id: str,
    limit: int = 100,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[models.HealthVitalReading]:
    """Get readings within date range or limit"""
    query = db.query(models.HealthVitalReading).filter(
        models.HealthVitalReading.device_id == device_id
    )

    if start_date:
        query = query.filter(models.HealthVitalReading.timestamp >= start_date)
    if end_date:
        query = query.filter(models.HealthVitalReading.timestamp <= end_date)

    return query.order_by(models.HealthVitalReading.timestamp.desc()).limit(limit).all()


def get_alerts(
    db: Session, device_id: str, limit: int = 50, severity: Optional[str] = None
) -> List[models.HealthAlert]:
    """Get alerts for device with optional filtering"""
    query = db.query(models.HealthAlert).filter(
        models.HealthAlert.device_id == device_id
    )

    if severity:
        query = query.filter(models.HealthAlert.severity == severity)

    return query.order_by(models.HealthAlert.timestamp.desc()).limit(limit).all()


def get_critical_alerts(db: Session, device_id: str) -> List[models.HealthAlert]:
    """Get only critical alerts"""
    return get_alerts(db, device_id, limit=20, severity="CRITICAL")


def acknowledge_alert(db: Session, alert_id: int):
    """Mark alert as acknowledged"""
    alert = (
        db.query(models.HealthAlert).filter(models.HealthAlert.id == alert_id).first()
    )
    if alert:
        alert.acknowledged = True
        alert.acknowledged_at = datetime.utcnow()
        db.commit()
        return {"status": "success"}
    return False


def calibrate_device(db: Session, device_id: str, resting_hr: int):
    """Set resting heart rate for temperature estimation calibration"""
    device = get_device(db, device_id)
    if device:
        device.resting_hr = resting_hr
        db.commit()
        return True
    return False


def get_thresholds(db: Session, device_id: str) -> List[models.HealthThreshold]:
    """Get alert thresholds for device"""
    return (
        db
        .query(models.HealthThreshold)
        .filter(models.HealthThreshold.device_id == device_id)
        .all()
    )


def set_thresholds(db: Session, device_id: str, thresholds: schemas.ThresholdConfig):
    """Update all alert thresholds for device"""
    device = get_device(db, device_id)
    if not device:
        return False

    # Helper to update or create
    def _upsert_threshold(t_type, t_value, enabled=True):
        db_thresh = (
            db
            .query(models.HealthThreshold)
            .filter(
                models.HealthThreshold.device_id == device_id,
                models.HealthThreshold.threshold_type == t_type,
            )
            .first()
        )
        if db_thresh:
            db_thresh.threshold_value = t_value
            db_thresh.enabled = enabled
        else:
            db_thresh = models.HealthThreshold(
                device_id=device_id,
                threshold_type=t_type,
                threshold_value=t_value,
                enabled=enabled,
            )
            db.add(db_thresh)

    # Update individual thresholds from the config object
    if thresholds.hr_high is not None:
        _upsert_threshold("HR_HIGH", thresholds.hr_high)
    if thresholds.hr_low is not None:
        _upsert_threshold("HR_LOW", thresholds.hr_low)
    if thresholds.spo2_low is not None:
        _upsert_threshold("SPO2_LOW", thresholds.spo2_low)
    if thresholds.spo2_critical is not None:
        _upsert_threshold("SPO2_CRITICAL", thresholds.spo2_critical)
    if thresholds.temp_high is not None:
        _upsert_threshold("TEMP_HIGH", thresholds.temp_high)
    if thresholds.temp_low is not None:
        _upsert_threshold("TEMP_LOW", thresholds.temp_low)

    db.commit()
    return True


def update_threshold(db: Session, device_id: str, threshold: schemas.ThresholdCreate):
    """Update or create a single threshold"""
    db_threshold = (
        db
        .query(models.HealthThreshold)
        .filter(
            models.HealthThreshold.device_id == device_id,
            models.HealthThreshold.threshold_type == threshold.threshold_type,
        )
        .first()
    )

    if db_threshold:
        db_threshold.threshold_value = threshold.threshold_value
        db_threshold.enabled = threshold.enabled
    else:
        db_threshold = models.HealthThreshold(
            device_id=device_id,
            threshold_type=threshold.threshold_type,
            threshold_value=threshold.threshold_value,
            enabled=threshold.enabled,
        )
        db.add(db_threshold)

    db.commit()
    db.refresh(db_threshold)
    return db_threshold


def get_summary_stats(db: Session, device_id: str, period: str = "daily"):
    """Get summary statistics for different time periods"""
    # Import here to avoid circular dependency if correlation_engine imports services
    from .correlation_engine import get_summary_stats as engine_stats

    return engine_stats(db, device_id, period)


def delete_device_vitals(db: Session, device_id: str) -> int:
    """Delete all vitals for a device, returns count"""
    count = (
        db
        .query(models.HealthVitalReading)
        .filter(models.HealthVitalReading.device_id == device_id)
        .delete()
    )
    db.commit()
    return count


def delete_device_alerts(db: Session, device_id: str) -> int:
    """Delete all alerts for a device, returns count"""
    count = (
        db
        .query(models.HealthAlert)
        .filter(models.HealthAlert.device_id == device_id)
        .delete()
    )
    db.commit()
    return count
