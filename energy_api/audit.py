from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .models import (
    EnergyAuditLog,
    EnergyDevice,
    EnergySensorConfig,
    EnergySensorReading,
)


def run_energy_audit(db: Session, device_id: str):
    """
    Analyzes latest readings and sensor configurations to generate waste alerts.
    """
    # Get device by device_id (string)
    device = db.query(EnergyDevice).filter(EnergyDevice.device_id == device_id).first()
    if not device:
        return []

    # Get latest reading
    latest = (
        db
        .query(EnergySensorReading)
        .filter(EnergySensorReading.device_id == device_id)
        .order_by(EnergySensorReading.timestamp.desc())
        .first()
    )

    if not latest:
        return []

    # Get sensor configs
    configs = (
        db
        .query(EnergySensorConfig)
        .filter(EnergySensorConfig.device_id == device_id)
        .all()
    )
    config_map = {c.sensor_number: c for c in configs}

    alerts = []

    # Analyze both sensors

    # Calculate daily usage for alert (Simplified)
    # Get readings for today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    todays_readings = (
        db
        .query(EnergySensorReading)
        .filter(
            EnergySensorReading.device_id == device_id,
            EnergySensorReading.timestamp >= today_start,
        )
        .all()
    )

    # Estimate kWh: Sum(watts) * 5 seconds / (3600 * 1000)
    total_watts_accumulated = sum(
        (r.sensor_1_watts or 0) + (r.sensor_2_watts or 0) for r in todays_readings
    )
    daily_kwh = (total_watts_accumulated * 5) / (3600 * 1000)

    # --- Rule 5: Daily Usage Alert ---
    DAILY_LIMIT_KWH = 20.0
    if daily_kwh > DAILY_LIMIT_KWH:
        alerts.append({
            "sensor": 0,  # System wide
            "type": "daily_limit_exceeded",
            "severity": "warning",
            "message": f"Daily usage ({daily_kwh:.2f} kWh) exceeded limit of {DAILY_LIMIT_KWH} kWh.",
            "waste_watts": 0,
        })

    for sensor_num in [1, 2]:
        config = config_map.get(sensor_num)
        current = getattr(latest, f"sensor_{sensor_num}_amps", 0)
        watts = getattr(latest, f"sensor_{sensor_num}_watts", 0)
        voltage = getattr(latest, f"sensor_{sensor_num}_voltage", 220.0)

        # --- Rule 6: Voltage Instability ---
        if voltage < 200.0:
            alerts.append({
                "sensor": sensor_num,
                "type": "voltage_brownout",
                "severity": "danger",
                "message": f"Low Voltage Detected ({voltage:.1f}V). Potential Brownout.",
                "waste_watts": 0,
            })
        elif voltage > 250.0:
            alerts.append({
                "sensor": sensor_num,
                "type": "voltage_surge",
                "severity": "danger",
                "message": f"High Voltage Detected ({voltage:.1f}V). Potential Surge.",
                "waste_watts": 0,
            })

        if watts < 5.0:  # Skip if device is effectively off
            continue

        label = config.custom_label.lower() if config else f"sensor {sensor_num}"
        category = config.appliance_category if config else "Unknown"

        # --- Rule 1: Lighting + High ambient light ---
        if "light" in label or category == "Lighting":
            if latest.light_lux > 800:
                alerts.append({
                    "sensor": sensor_num,
                    "type": "lighting_waste",
                    "severity": "warning",
                    "message": f"{label}: Lights ON but sufficient natural light ({latest.light_lux} lux)",
                    "waste_watts": watts,
                })

            # --- Rule 1b: Night Time Curfew (11 PM - 5 AM) ---
            current_hour = (
                datetime.utcnow().hour
            )  # Using UTC, might need adjustment for local time
            # Assuming Nigeria is UTC+1, 23:00 UTC is 00:00 Local.
            # Local 11 PM (23:00) to 5 AM (05:00)
            # UTC 10 PM (22:00) to 4 AM (04:00)
            # Let's stick to a simple UTC check for now or approximate
            if current_hour >= 23 or current_hour < 5:
                alerts.append({
                    "sensor": sensor_num,
                    "type": "lighting_curfew_waste",
                    "severity": "warning",
                    "message": f"{label}: Lights ON during curfew hours (11 PM - 5 AM).",
                    "waste_watts": watts,
                })

        # --- Rule 2: HVAC + Temperature ---
        # 2a. Air Conditioning Logic
        if category == "AC" or any(x in label for x in ["ac", "cooling", "air con"]):
            # Alert if AC is ON (> 200W) but room is already cold (< 21°C) AND it's not hot outside (< 24°C)
            if watts > 200 and latest.temperature_c and latest.outdoor_temp_c:
                if latest.temperature_c < 21.0 and latest.outdoor_temp_c < 24.0:
                    alerts.append({
                        "sensor": sensor_num,
                        "type": "hvac_inefficient_use",
                        "severity": "warning",
                        "message": f"{label}: AC is running but it's cool inside ({latest.temperature_c}°C) and outside ({latest.outdoor_temp_c}°C). Consider turning off.",
                        "waste_watts": watts,
                    })

            # Cooling check (Standard Overcooling)
            if latest.temperature_c and latest.temperature_c < 20:
                alerts.append({
                    "sensor": sensor_num,
                    "type": "hvac_overcooling",
                    "severity": "warning",
                    "message": f"{label}: Cooling at {watts:.0f}W but room is 20°C or colder ({latest.temperature_c}°C)",
                    "waste_watts": watts * 0.5,
                })

            # --- Rule 4: Free Cooling Opportunity ---
            # If AC is ON and Outdoor Temp is significantly cooler than Indoor Temp
            if latest.outdoor_temp_c and latest.temperature_c:
                if (latest.temperature_c - latest.outdoor_temp_c) > 3.0:
                    alerts.append({
                        "sensor": sensor_num,
                        "type": "free_cooling_avail",
                        "severity": "info",
                        "message": f"{label}: AC ON but it is cooler outside ({latest.outdoor_temp_c}°C). Open windows.",
                        "waste_watts": watts,
                    })

        # 2b. Heater Logic
        if category == "Heater" or any(x in label for x in ["heater", "heating"]):
            # Alert if Heater is ON (> 200W) but room is hot (> 25°C) AND outdoor is mild (> 20°C)
            if watts > 200 and latest.temperature_c and latest.outdoor_temp_c:
                if latest.temperature_c > 25.0 and latest.outdoor_temp_c > 20.0:
                    alerts.append({
                        "sensor": sensor_num,
                        "type": "hvac_inefficient_use",
                        "severity": "warning",
                        "message": f"{label}: Heater running but it's warm inside ({latest.temperature_c}°C) and outside ({latest.outdoor_temp_c}°C).",
                        "waste_watts": watts,
                    })

        if any(x in label for x in ["heater", "heating"]) or category == "HVAC":
            # Heating check
            if latest.temperature_c and latest.temperature_c > 26:
                alerts.append({
                    "sensor": sensor_num,
                    "type": "hvac_overheating",
                    "severity": "warning",
                    "message": f"{label}: Heating at {watts:.0f}W but room is 26°C or warmer ({latest.temperature_c}°C)",
                    "waste_watts": watts * 0.6,
                })

        # --- Rule 3: Phantom Loads ---
        # If current is very low but non-zero for a long time (simplified check here)
        if 0.02 < current < 0.2:
            alerts.append({
                "sensor": sensor_num,
                "type": "phantom_load",
                "severity": "info",
                "message": f"{label}: Drawing {watts:.1f}W standby power",
                "waste_watts": watts,
            })

    # Save alerts to DB
    for alert in alerts:
        # Check if identical alert exists recently (deduplication)
        recent = (
            db
            .query(EnergyAuditLog)
            .filter(
                EnergyAuditLog.device_id == device_id,
                EnergyAuditLog.sensor_number == alert["sensor"],
                EnergyAuditLog.audit_type == alert["type"],
                EnergyAuditLog.timestamp > datetime.utcnow() - timedelta(minutes=10),
            )
            .first()
        )

        if not recent:
            log = EnergyAuditLog(
                device_id=device_id,
                sensor_number=alert["sensor"],
                audit_type=alert["type"],
                severity=alert["severity"],
                message=alert["message"],
                estimated_waste_watts=alert["waste_watts"],
            )
            db.add(log)

    db.commit()
    return alerts
