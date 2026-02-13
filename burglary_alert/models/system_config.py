"""System configuration model."""

from database import Base
from sqlalchemy import Column, Integer, String


class SystemConfig(Base):
    """System configuration (singleton table)."""

    __tablename__ = "burglary_system_config"

    id = Column(Integer, primary_key=True, index=True)
    emergency_phone = Column(String, nullable=True)
    device_api_key = Column(String, nullable=False)

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "emergency_phone": self.emergency_phone,
            "device_api_key": self.device_api_key,
        }
