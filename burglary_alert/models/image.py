"""Image model for captured security images."""

import enum
from datetime import datetime

from database import Base
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship


class ImageSource(str, enum.Enum):
    """Source of the image."""

    ESP32_CAM = "esp32_cam"


class Image(Base):
    """Image model representing captured security photos."""

    __tablename__ = "burglary_images"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    image_path = Column(String, nullable=False)  # Filename in uploads/burglary/
    thumbnail_path = Column(String, nullable=True)
    file_size = Column(Integer, nullable=False)  # Size in bytes
    alert_id = Column(Integer, ForeignKey("burglary_alerts.id"), nullable=True)
    received_from = Column(
        Enum(ImageSource), default=ImageSource.ESP32_CAM, nullable=False
    )

    # Relationship
    alert = relationship("Alert", back_populates="image", foreign_keys=[alert_id])

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "image_url": self.image_path,
            "thumbnail_url": self.thumbnail_path,
            "file_size": self.file_size,
            "alert_id": self.alert_id,
            "received_from": self.received_from.value if self.received_from else None,
        }
