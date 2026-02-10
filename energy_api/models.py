from database import Base  # Importing Base from the main app's database.py
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class EnergyDevice(Base):
    __tablename__ = "energy_devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), unique=True, nullable=False, index=True)
    device_name = Column(String(100))
    location = Column(String(100))
    voltage_setting = Column(Float, default=220.0)
    power_factor = Column(Float, default=0.95)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True))

    sensor_configs = relationship("EnergySensorConfig", back_populates="device")
    readings = relationship("EnergySensorReading", back_populates="device")
    audit_logs = relationship("EnergyAuditLog", back_populates="device")
    cost_settings = relationship(
        "EnergyCostSettings", back_populates="device", uselist=False
    )
    energy_goals = relationship("EnergyGoal", back_populates="device")


class EnergySensorConfig(Base):
    __tablename__ = "energy_sensor_config"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), ForeignKey("energy_devices.device_id"))
    sensor_number = Column(Integer)  # 1 or 2
    custom_label = Column(String(100), nullable=False)
    appliance_category = Column(String(50))
    user_notes = Column(Text)

    device = relationship("EnergyDevice", back_populates="sensor_configs")

    __table_args__ = (
        UniqueConstraint("device_id", "sensor_number", name="uix_device_sensor"),
    )


class EnergySensorReading(Base):
    __tablename__ = "energy_sensor_readings"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), ForeignKey("energy_devices.device_id"))
    timestamp = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    sensor_1_amps = Column(Float)
    sensor_1_watts = Column(Float)
    sensor_1_voltage = Column(Float)
    sensor_2_amps = Column(Float)
    sensor_2_watts = Column(Float)
    sensor_2_voltage = Column(Float)

    temperature_c = Column(Float)
    humidity_percent = Column(Float)
    light_raw = Column(Integer)
    light_lux = Column(Integer)
    outdoor_temp_c = Column(Float)  # From Open-Meteo

    device = relationship("EnergyDevice", back_populates="readings")


class EnergyAuditLog(Base):
    __tablename__ = "energy_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), ForeignKey("energy_devices.device_id"))
    timestamp = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    sensor_number = Column(Integer)
    audit_type = Column(String(50))
    severity = Column(String(20))
    message = Column(Text)
    estimated_waste_watts = Column(Float)

    device = relationship("EnergyDevice", back_populates="audit_logs")


class EnergyCostSettings(Base):
    __tablename__ = "energy_cost_settings"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), ForeignKey("energy_devices.device_id"))
    currency = Column(String(10), default="USD")
    cost_per_kwh = Column(Float, default=0.12)
    billing_cycle_start = Column(Integer, default=1)

    device = relationship("EnergyDevice", back_populates="cost_settings")


class EnergyGoal(Base):
    __tablename__ = "energy_goals"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), ForeignKey("energy_devices.device_id"))
    target_kwh = Column(Float, nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)  # e.g., 2026-02-01
    period_end = Column(DateTime(timezone=True), nullable=False)  # e.g., 2026-03-01

    device = relationship("EnergyDevice", back_populates="energy_goals")
