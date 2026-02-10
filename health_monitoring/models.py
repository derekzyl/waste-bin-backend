"""
Health Monitoring Database Models
All tables use 'health_' prefix to avoid conflicts with other modules
"""

import datetime

from database import Base
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship


class HealthDevice(Base):
    """Health monitoring device registration"""

    __tablename__ = "health_devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), unique=True, nullable=False, index=True)
    device_name = Column(String(100))
    user_name = Column(String(100))
    date_of_birth = Column(Date)
    gender = Column(String(20))
    resting_hr = Column(Integer, default=70)  # Baseline for Liebermeister's Rule
    is_athlete = Column(Boolean, default=False)  # Athletes have lower resting HR
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_seen = Column(DateTime)
    firmware_version = Column(String(20))

    vital_readings = relationship("HealthVitalReading", back_populates="device")
    alerts = relationship("HealthAlert", back_populates="device")
    thresholds = relationship("HealthThreshold", back_populates="device")
    daily_summaries = relationship("HealthDailySummary", back_populates="device")


class HealthVitalReading(Base):
    """Individual vital signs reading (HR + SpO2 + Temperature)"""

    __tablename__ = "health_vital_readings"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(
        String(50), ForeignKey("health_devices.device_id"), nullable=False
    )
    timestamp = Column(DateTime, nullable=False, index=True)

    # Heart Rate data (from Sen-11574)
    heart_rate = Column(Integer)  # BPM
    hr_signal_quality = Column(Integer)  # 0-100
    is_hr_valid = Column(Boolean, default=True)

    # SpO2 data (from Sen-11574)
    spo2 = Column(Integer)  # Percentage (0-100)
    spo2_signal_quality = Column(Integer)  # 0-100
    is_spo2_valid = Column(Boolean, default=True)

    # Temperature data (from DS18B20 or estimated)
    temperature = Column(Float)  # Celsius
    temp_source = Column(String(20))  # 'DS18B20' or 'ESTIMATED'
    is_temp_estimated = Column(Boolean, default=False)

    # System data
    battery_percent = Column(Integer)
    battery_voltage = Column(Float)
    wifi_rssi = Column(Integer)
    uptime_seconds = Column(Integer)

    device = relationship("HealthDevice", back_populates="vital_readings")


class HealthAlert(Base):
    """Health alerts (critical SpO2, fever, etc.)"""

    __tablename__ = "health_alerts"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), ForeignKey("health_devices.device_id"))
    timestamp = Column(DateTime, nullable=False, index=True)
    alert_type = Column(String(50))  # 'HYPOXIA', 'FEVER', 'TACHYCARDIA', etc.
    severity = Column(String(20))  # 'INFO', 'WARNING', 'CRITICAL'
    message = Column(Text)
    vital_snapshot = Column(JSON)  # Store HR, SpO2, Temp at time of alert
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime)

    device = relationship("HealthDevice", back_populates="alerts")


class HealthThreshold(Base):
    """User-configurable alert thresholds"""

    __tablename__ = "health_thresholds"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), ForeignKey("health_devices.device_id"))
    threshold_type = Column(String(50))  # 'HR_HIGH', 'HR_LOW', 'SPO2_LOW', 'TEMP_HIGH'
    threshold_value = Column(Float)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    device = relationship("HealthDevice", back_populates="thresholds")


class HealthDailySummary(Base):
    """Daily aggregated health statistics"""

    __tablename__ = "health_daily_summary"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), ForeignKey("health_devices.device_id"))
    date = Column(Date, nullable=False)

    # Heart rate stats
    avg_hr = Column(Float)
    min_hr = Column(Integer)
    max_hr = Column(Integer)

    # SpO2 stats
    avg_spo2 = Column(Float)
    min_spo2 = Column(Integer)

    # Temperature stats
    avg_temp = Column(Float)
    min_temp = Column(Float)
    max_temp = Column(Float)
    temp_estimated_percent = Column(Float)  # % of readings that were estimated

    # Alert stats
    total_alerts = Column(Integer)
    hypoxia_events = Column(Integer)  # SpO2 < 90%

    device = relationship("HealthDevice", back_populates="daily_summaries")
