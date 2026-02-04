"""
SQLAlchemy database models
"""

import uuid

from database import Base
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.sql import func


class Bin(Base):
    """Bin model for storing waste bin information"""

    __tablename__ = "bins"

    id = Column(
        String, primary_key=True, default=lambda: f"0x{str(uuid.uuid4().int)[:3]}"
    )
    type = Column(String, nullable=False)  # 'organic' or 'non_organic'
    weight = Column(Float, default=0.0)
    level = Column(Integer, default=0)  # 0-100 percentage
    full = Column(Boolean, default=False)
    last_update = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "type": self.type,
            "weight": self.weight,
            "level": self.level,
            "full": self.full,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DetectionLog(Base):
    """Log of material detections"""

    __tablename__ = "detection_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    material = Column(String, nullable=False)  # 'ORGANIC' or 'NON_ORGANIC'
    confidence = Column(Float, nullable=False)
    method = Column(String)  # 'ml_model' or 'rule_based'
    bin_id = Column(String)  # Associated bin ID
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    image_path = Column(Text, nullable=True)  # Optional path to stored image

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "material": self.material,
            "confidence": self.confidence,
            "method": self.method,
            "bin_id": self.bin_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "image_path": self.image_path,
        }


class BinEvent(Base):
    """Log of bin events (open, close, reset, etc.)"""

    __tablename__ = "bin_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    bin_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)  # 'open', 'close', 'reset', 'full'
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    event_metadata = Column(Text, nullable=True)  # JSON string for additional data

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "bin_id": self.bin_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.event_metadata,
        }
