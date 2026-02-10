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


def store_vitals(
    db: Session, vitals: schemas.VitalReadingCreate
) -> models.HealthVitalReading:
    """Store vital signs reading"""
    # Ensure device exists
    device = get_device(db, vitals.device_id)
    if not device:
        # Auto-create device if not exists
        create_device(db, schemas.DeviceCreate(device_id=vitals.device_id))

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
    return reading


def update_last_seen(db: Session, device_id: str):
    """Update device last seen timestamp"""
    device = get_device(db, device_id)
    if device:
        device.last_seen = datetime.utcnow()
        db.commit()


def get_latest_reading(
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


def get_readings_range(
    db: Session,
    device_id: str,
    start_date: datetime,
    end_date: datetime,
    limit: int = 100,
) -> List[models.HealthVitalReading]:
    """Get readings within date range"""
    return (
        db
        .query(models.HealthVitalReading)
        .filter(
            models.HealthVitalReading.device_id == device_id,
            models.HealthVitalReading.timestamp >= start_date,
            models.HealthVitalReading.timestamp <= end_date,
        )
        .order_by(models.HealthVitalReading.timestamp.desc())
        .limit(limit)
        .all()
    )


def get_device_alerts(db: Session, device_id: str) -> List[models.HealthAlert]:
    """Get all alerts for device"""
    return (
        db
        .query(models.HealthAlert)
        .filter(models.HealthAlert.device_id == device_id)
        .order_by(models.HealthAlert.timestamp.desc())
        .all()
    )


def get_critical_alerts(db: Session, device_id: str) -> List[models.HealthAlert]:
    """Get only critical alerts"""
    return (
        db
        .query(models.HealthAlert)
        .filter(
            models.HealthAlert.device_id == device_id,
            models.HealthAlert.severity == "CRITICAL",
        )
        .order_by(models.HealthAlert.timestamp.desc())
        .all()
    )


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
    return {"status": "not_found"}


def set_resting_hr(db: Session, device_id: str, resting_hr: int):
    """Set resting heart rate for temperature estimation calibration"""
    device = get_device(db, device_id)
    if device:
        device.resting_hr = resting_hr
        db.commit()
        return {"status": "success", "resting_hr": resting_hr}
    return {"status": "device_not_found"}


def get_thresholds(db: Session, device_id: str) -> List[models.HealthThreshold]:
    """Get alert thresholds for device"""
    return (
        db
        .query(models.HealthThreshold)
        .filter(models.HealthThreshold.device_id == device_id)
        .all()
    )


def update_threshold(db: Session, device_id: str, threshold: schemas.ThresholdCreate):
    """Update or create threshold"""
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
