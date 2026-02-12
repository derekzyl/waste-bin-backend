"""Telegram configuration model."""

from database import Base
from sqlalchemy import Boolean, Column, Integer, String


class TelegramConfig(Base):
    """Telegram bot configuration (singleton table)."""

    __tablename__ = "burglary_telegram_config"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String, nullable=True)
    bot_token = Column(String, nullable=True)
    active = Column(Boolean, default=False, nullable=False)

    def to_dict(self, mask_token=True):
        """Convert model to dictionary."""
        token = self.bot_token
        if mask_token and token:
            # Mask token except last 6 characters
            token = "*" * (len(token) - 6) + token[-6:] if len(token) > 6 else "******"

        return {
            "id": self.id,
            "chat_id": self.chat_id,
            "bot_token": token,
            "active": self.active,
        }
