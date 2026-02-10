"""
Health Correlation Engine
Analyzes vital signs patterns and generates intelligent alerts
"""

import statistics
from datetime import datetime, timedelta
from typing import Dict, List

from sqlalchemy.orm import Session

from . import models, schemas


def analyze_vitals(
    db: Session, vitals_data: schemas.VitalReadingCreate
) -> List[models.HealthAlert]:
    """
    Real-time analysis of incoming vitals (HR + SpO2 + Temp)
    Returns list of generated alerts
    """
    device = (
        db
        .query(models.HealthDevice)
        .filter(models.HealthDevice.device_id == vitals_data.device_id)
        .first()
    )

    if not device:
        return []

    # Get thresholds
    thresholds = (
        db
        .query(models.HealthThreshold)
        .filter(
            models.HealthThreshold.device_id == vitals_data.device_id,
            models.HealthThreshold.enabled,
        )
        .all()
    )

    threshold_dict = {t.threshold_type: t.threshold_value for t in thresholds}

    alerts = []
    hr = vitals_data.vitals.heart_rate.bpm
    spo2 = vitals_data.vitals.spo2.percent if vitals_data.vitals.spo2.is_valid else 0
    temp = vitals_data.vitals.temperature.celsius
    is_temp_estimated = vitals_data.vitals.temperature.is_estimated

    # CRITICAL ALERT: Severe Hypoxia (SpO2 < 90%)
    if spo2 > 0 and spo2 < threshold_dict.get("SPO2_CRITICAL", 90):
        alert = create_alert(
            db,
            vitals_data.device_id,
            "CRITICAL_HYPOXIA",
            "CRITICAL",
            f"CRITICAL: Blood oxygen at {spo2}% - SEEK IMMEDIATE MEDICAL ATTENTION",
            vitals_data,
        )
        alerts.append(alert)

    # WARNING: Low SpO2 (90-94%)
    elif spo2 > 0 and spo2 < threshold_dict.get("SPO2_LOW", 95):
        alert = create_alert(
            db,
            vitals_data.device_id,
            "LOW_SPO2",
            "WARNING",
            f"Low blood oxygen: {spo2}% (normal >95%)",
            vitals_data,
        )
        alerts.append(alert)

    # CRITICAL: Respiratory Distress Pattern (High HR + Low SpO2)
    if spo2 > 0 and spo2 < 94 and hr > 90:
        alert = create_alert(
            db,
            vitals_data.device_id,
            "RESPIRATORY_DISTRESS",
            "CRITICAL",
            f"Pattern suggests respiratory distress: SpO2 {spo2}%, HR {hr} BPM",
            vitals_data,
        )
        alerts.append(alert)

    # WARNING: Infection Pattern (Fever + Tachycardia + Low SpO2)
    if temp > 37.5 and hr > 90 and spo2 > 0 and spo2 < 96:
        alert = create_alert(
            db,
            vitals_data.device_id,
            "INFECTION_PATTERN",
            "WARNING",
            f"Possible respiratory infection: Temp {temp}°C, HR {hr}, SpO2 {spo2}%",
            vitals_data,
        )
        alerts.append(alert)

    # WARNING: Fever Detection
    if temp > threshold_dict.get("TEMP_HIGH", 38.0):
        if hr > threshold_dict.get("HR_HIGH", 100):
            alert = create_alert(
                db,
                vitals_data.device_id,
                "FEVER",
                "WARNING",
                f"Fever detected: {temp}°C with elevated HR ({hr} BPM)",
                vitals_data,
            )
            alerts.append(alert)
        else:
            alert = create_alert(
                db,
                vitals_data.device_id,
                "HIGH_TEMP",
                "WARNING",
                f"Elevated temperature: {temp}°C",
                vitals_data,
            )
            alerts.append(alert)

    # WARNING: Tachycardia
    if hr > threshold_dict.get("HR_HIGH", 100):
        alert = create_alert(
            db,
            vitals_data.device_id,
            "TACHYCARDIA",
            "WARNING",
            f"Elevated heart rate: {hr} BPM",
            vitals_data,
        )
        alerts.append(alert)

    # WARNING: Bradycardia (non-athletes only)
    if hr < threshold_dict.get("HR_LOW", 50) and hr > 0 and not device.is_athlete:
        alert = create_alert(
            db,
            vitals_data.device_id,
            "BRADYCARDIA",
            "WARNING",
            f"Low heart rate: {hr} BPM",
            vitals_data,
        )
        alerts.append(alert)

    # INFO: Temperature estimation during high HR (unreliable)
    if is_temp_estimated and hr > 100:
        alert = create_alert(
            db,
            vitals_data.device_id,
            "TEMP_EST_UNRELIABLE",
            "INFO",
            f"Temperature estimated - may be inaccurate during high HR ({hr} BPM)",
            vitals_data,
        )
        alerts.append(alert)

    # CRITICAL: Hypothermia
    if temp < threshold_dict.get("TEMP_LOW", 35.5):
        alert = create_alert(
            db,
            vitals_data.device_id,
            "HYPOTHERMIA",
            "CRITICAL",
            f"Low body temperature: {temp}°C",
            vitals_data,
        )
        alerts.append(alert)

    # CRITICAL: Severe Infection (High HR + Low SpO2 + Fever)
    if spo2 > 0 and spo2 < 90 and hr > 90 and temp > 37.5:
        alert = create_alert(
            db,
            vitals_data.device_id,
            "SEVERE_INFECTION",
            "CRITICAL",
            "CRITICAL: Severe respiratory infection pattern detected",
            vitals_data,
        )
        alerts.append(alert)

    return alerts


def create_alert(
    db: Session,
    device_id: str,
    alert_type: str,
    severity: str,
    message: str,
    vitals_data: schemas.VitalReadingCreate,
) -> models.HealthAlert:
    """Create and store alert"""
    alert = models.HealthAlert(
        device_id=device_id,
        timestamp=datetime.utcnow(),
        alert_type=alert_type,
        severity=severity,
        message=message,
        vital_snapshot={
            "hr": vitals_data.vitals.heart_rate.bpm,
            "hr_quality": vitals_data.vitals.heart_rate.signal_quality,
            "spo2": vitals_data.vitals.spo2.percent
            if vitals_data.vitals.spo2.is_valid
            else 0,
            "spo2_quality": vitals_data.vitals.spo2.signal_quality,
            "temp": vitals_data.vitals.temperature.celsius,
            "temp_source": vitals_data.vitals.temperature.source,
        },
    )
    db.add(alert)
    db.commit()
    return alert


def analyze_health_patterns(db: Session, device_id: str, hours: int = 24) -> Dict:
    """Multi-variate health analysis (HR + SpO2 + Temp)"""
    start_time = datetime.utcnow() - timedelta(hours=hours)

    readings = (
        db
        .query(models.HealthVitalReading)
        .filter(
            models.HealthVitalReading.device_id == device_id,
            models.HealthVitalReading.timestamp >= start_time,
        )
        .all()
    )

    if not readings:
        return {"message": "No data available"}

    patterns = []

    # Temperature trend analysis
    temps = [r.temperature for r in readings if r.temperature]
    if temps and is_increasing_trend(temps):
        patterns.append({
            "type": "FEVER_PROGRESSION",
            "message": f"Temperature rising: {min(temps):.1f}°C → {max(temps):.1f}°C",
            "severity": "WARNING",
        })

    # SpO2 trend analysis
    spo2_values = [r.spo2 for r in readings if r.spo2 and r.is_spo2_valid]
    if spo2_values:
        avg_spo2 = statistics.mean(spo2_values)
        if avg_spo2 < 95:
            low_count = sum(1 for s in spo2_values if s < 95)
            patterns.append({
                "type": "CHRONIC_LOW_SPO2",
                "message": f"Low SpO2 for {(low_count / len(spo2_values)) * 100:.0f}% of period (avg {avg_spo2:.1f}%)",
                "severity": "WARNING",
            })

    # Compensatory tachycardia (body trying to compensate for low O2)
    low_spo2_readings = [r for r in readings if r.spo2 and r.spo2 < 94]
    if len(low_spo2_readings) > 5:
        avg_hr_during_low = statistics.mean([
            r.heart_rate for r in low_spo2_readings if r.heart_rate
        ])
        if avg_hr_during_low > 90:
            patterns.append({
                "type": "COMPENSATORY_TACHYCARDIA",
                "message": f"Heart rate elevated ({avg_hr_during_low:.0f} BPM) during low SpO2 episodes",
                "severity": "CRITICAL",
            })

    # Temperature estimation reliability
    est_readings = [r for r in readings if r.is_temp_estimated]
    if est_readings:
        est_percent = (len(est_readings) / len(readings)) * 100
        if est_percent > 50:
            patterns.append({
                "type": "TEMP_SENSOR_ISSUE",
                "message": f"{est_percent:.0f}% of readings estimated - check DS18B20 sensor",
                "severity": "INFO",
            })

    # Calculate summary stats
    hr_values = [r.heart_rate for r in readings if r.heart_rate]

    summary = {
        "avg_hr": round(statistics.mean(hr_values), 1) if hr_values else 0,
        "avg_spo2": round(statistics.mean(spo2_values), 1) if spo2_values else 0,
        "avg_temp": round(statistics.mean(temps), 1) if temps else 0,
        "temp_estimated_percent": round((len(est_readings) / len(readings)) * 100, 1),
        "hypoxia_events": sum(1 for r in readings if r.spo2 and r.spo2 < 90),
    }

    return {
        "analysis_period_hours": hours,
        "total_readings": len(readings),
        "patterns": patterns,
        "summary": summary,
    }


def get_summary_stats(db: Session, device_id: str, period: str = "daily") -> Dict:
    """Get summary statistics for specified period"""
    if period == "daily":
        start_time = datetime.utcnow() - timedelta(days=1)
    elif period == "weekly":
        start_time = datetime.utcnow() - timedelta(weeks=1)
    elif period == "monthly":
        start_time = datetime.utcnow() - timedelta(days=30)
    else:
        start_time = datetime.utcnow() - timedelta(days=1)

    readings = (
        db
        .query(models.HealthVitalReading)
        .filter(
            models.HealthVitalReading.device_id == device_id,
            models.HealthVitalReading.timestamp >= start_time,
        )
        .all()
    )

    if not readings:
        return {"message": "No data available"}

    hr_values = [r.heart_rate for r in readings if r.heart_rate]
    spo2_values = [r.spo2 for r in readings if r.spo2 and r.is_spo2_valid]
    temp_values = [r.temperature for r in readings if r.temperature]

    return {
        "period": period,
        "heart_rate": {
            "avg": round(statistics.mean(hr_values), 1) if hr_values else 0,
            "min": min(hr_values) if hr_values else 0,
            "max": max(hr_values) if hr_values else 0,
        },
        "spo2": {
            "avg": round(statistics.mean(spo2_values), 1) if spo2_values else 0,
            "min": min(spo2_values) if spo2_values else 0,
        },
        "temperature": {
            "avg": round(statistics.mean(temp_values), 1) if temp_values else 0,
            "min": round(min(temp_values), 1) if temp_values else 0,
            "max": round(max(temp_values), 1) if temp_values else 0,
        },
        "total_readings": len(readings),
    }


def is_increasing_trend(values: List[float]) -> bool:
    """Check if values show increasing trend"""
    if len(values) < 3:
        return False
    first_third = statistics.mean(values[: len(values) // 3])
    last_third = statistics.mean(values[-len(values) // 3 :])
    return last_third > first_third * 1.05
