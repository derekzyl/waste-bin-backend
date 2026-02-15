"""Device status model."""

from datetime import datetime

from database import Base
from sqlalchemy import Column, DateTime, String


class DeviceStatus(Base):
    """Device status table."""

    __tablename__ = "burglary_device_status"

    device_id = Column(String, primary_key=True, index=True)
    status = Column(String, default="offline")  # online, offline
    ip_address = Column(String, nullable=True)
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    firmware_version = Column(String, nullable=True)

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "device_id": self.device_id,
            "status": self.status,
            "ip_address": self.ip_address,
            "last_heartbeat": self.last_heartbeat.isoformat()
            if self.last_heartbeat
            else None,
            "firmware_version": self.firmware_version,
        }
