"""
Pydantic schemas for Health Monitoring API
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

# ==================== DEVICE SCHEMAS ====================


class DeviceCreate(BaseModel):
    device_id: str
    device_name: Optional[str] = None
    user_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    resting_hr: Optional[int] = 70
    is_athlete: Optional[bool] = False


class DeviceResponse(BaseModel):
    id: int
    device_id: str
    device_name: Optional[str]
    user_name: Optional[str]
    resting_hr: int
    is_athlete: bool
    created_at: datetime
    last_seen: Optional[datetime]

    class Config:
        from_attributes = True


# ==================== VITAL READING SCHEMAS ====================


class HeartRateData(BaseModel):
    bpm: int
    signal_quality: int = Field(..., ge=0, le=100)
    is_valid: bool


class SpO2Data(BaseModel):
    percent: int = Field(..., ge=0, le=100)
    signal_quality: int = Field(..., ge=0, le=100)
    is_valid: bool


class TemperatureData(BaseModel):
    celsius: float
    source: str  # 'DS18B20' or 'ESTIMATED'
    is_estimated: bool


class SystemData(BaseModel):
    battery_percent: int = Field(default=100, ge=0, le=100)
    battery_voltage: float = Field(default=3.7)
    wifi_rssi: int
    uptime_seconds: int
    monitoring_state: Optional[str] = "idle"  # 'idle', 'monitoring', or 'paused'


class VitalsData(BaseModel):
    heart_rate: HeartRateData
    spo2: SpO2Data
    temperature: TemperatureData


class AlertData(BaseModel):
    type: str
    message: str


class VitalReadingCreate(BaseModel):
    device_id: str
    timestamp: int  # Unix timestamp
    vitals: VitalsData
    system: SystemData
    alerts: Optional[List[AlertData]] = []


class VitalReadingResponse(BaseModel):
    status: str
    reading_id: int
    alerts_generated: int
    critical_alerts: List[dict]


class VitalReadingDetailed(BaseModel):
    id: int
    device_id: str
    timestamp: datetime
    heart_rate: int
    hr_signal_quality: int
    spo2: int
    spo2_signal_quality: int
    temperature: float
    temp_source: str
    is_temp_estimated: bool
    battery_percent: int

    class Config:
        from_attributes = True


# ==================== ALERT SCHEMAS ====================


class AlertResponse(BaseModel):
    id: int
    device_id: str
    timestamp: datetime
    alert_type: str
    severity: str
    message: str
    vital_snapshot: dict
    acknowledged: bool

    class Config:
        from_attributes = True


# ==================== THRESHOLD SCHEMAS ====================


class ThresholdCreate(BaseModel):
    threshold_type: str  # 'HR_HIGH', 'HR_LOW', 'SPO2_LOW', 'TEMP_HIGH'
    threshold_value: float
    enabled: bool = True


class ThresholdResponse(BaseModel):
    id: int
    device_id: str
    threshold_type: str
    threshold_value: float
    enabled: bool

    class Config:
        from_attributes = True


class ThresholdConfig(BaseModel):
    hr_high: Optional[float] = Field(None, description="Upper heart rate limit")
    hr_low: Optional[float] = Field(None, description="Lower heart rate limit")
    spo2_low: Optional[float] = Field(None, description="Low SpO2 warning limit")
    spo2_critical: Optional[float] = Field(None, description="Critical SpO2 limit")
    temp_high: Optional[float] = Field(None, description="High temperature limit")
    temp_low: Optional[float] = Field(None, description="Low temperature limit")


# ==================== CALIBRATION SCHEMAS ====================


class CalibrationRequest(BaseModel):
    resting_hr: int = Field(..., ge=40, le=100)


# Alias for backward compatibility if needed, or just use CalibrationRequest
RestingHRCalibration = CalibrationRequest


class ThresholdConfig(BaseModel):
    thresholds: List[ThresholdResponse]


# ==================== STATE CONTROL SCHEMAS ====================


class StateCommand(BaseModel):
    state: str  # 'idle', 'monitoring', or 'paused'
