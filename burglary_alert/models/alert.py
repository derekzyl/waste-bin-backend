"""Alert model for burglary detection events."""

from datetime import datetime

from database import Base
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship


class Alert(Base):
    """Alert model representing a motion detection event."""

    __tablename__ = "burglary_alerts"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    alert_type = Column(String, default="motion", nullable=False)
    detection_confidence = Column(Float, nullable=False)
    pir_sensors_triggered = Column(
        JSON, nullable=False
    )  # {"left": bool, "middle": bool, "right": bool}
    network_status = Column(String, nullable=False)  # "online", "offline"
    image_id = Column(Integer, ForeignKey("burglary_images.id"), nullable=True)
    correlated = Column(Boolean, default=False, nullable=False)

    # Relationship
    # Relationship
    image = relationship(
        "Image", back_populates="alert", uselist=False, foreign_keys="Image.alert_id"
    )

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "alert_type": self.alert_type,
            "detection_confidence": self.detection_confidence,
            "pir_sensors_triggered": self.pir_sensors_triggered,
            "network_status": self.network_status,
            "image_id": self.image_id,
            "correlated": self.correlated,
            "image_url": f"/uploads/burglary/{self.image.image_path}"
            if self.image
            else None,
        }
