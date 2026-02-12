"""Telegram configuration router."""

from typing import Optional

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..models.telegram_config import TelegramConfig
from ..services.telegram_bot import TelegramBot
from ..utils.auth import get_current_user

router = APIRouter(prefix="/telegram", tags=["Telegram"])


class TelegramConfigRequest(BaseModel):
    """Telegram configuration request model."""

    chat_id: str
    bot_token: str
    active: bool = True


class TelegramConfigResponse(BaseModel):
    """Telegram configuration response model."""

    chat_id: Optional[str]
    bot_token: str  # Masked
    active: bool


class TelegramTestResponse(BaseModel):
    """Telegram test response model."""

    status: str
    message: str


@router.post("/config")
async def save_telegram_config(
    config: TelegramConfigRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    Set Telegram bot token and chat ID.

    Requires JWT authentication.
    """
    # Get or create config (singleton)
    telegram_config = db.query(TelegramConfig).first()

    if telegram_config:
        # Update existing
        telegram_config.chat_id = config.chat_id
        telegram_config.bot_token = config.bot_token
        telegram_config.active = config.active
    else:
        # Create new
        telegram_config = TelegramConfig(
            chat_id=config.chat_id,
            bot_token=config.bot_token,
            active=config.active,
        )
        db.add(telegram_config)

    db.commit()
    db.refresh(telegram_config)

    return {
        "status": "success",
        "message": "Telegram configuration saved",
    }


@router.get("/config", response_model=TelegramConfigResponse)
async def get_telegram_config(
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    Get current Telegram configuration (masked token).

    Requires JWT authentication.
    """
    telegram_config = db.query(TelegramConfig).first()

    if not telegram_config:
        return TelegramConfigResponse(
            chat_id=None,
            bot_token="Not configured",
            active=False,
        )

    # Mask token
    config_dict = telegram_config.to_dict(mask_token=True)

    return TelegramConfigResponse(
        chat_id=config_dict["chat_id"],
        bot_token=config_dict["bot_token"],
        active=config_dict["active"],
    )


@router.post("/test", response_model=TelegramTestResponse)
async def test_telegram_connection(
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    Test Telegram bot connection.

    Requires JWT authentication.
    """
    telegram_config = db.query(TelegramConfig).first()

    if not telegram_config or not telegram_config.bot_token:
        raise HTTPException(status_code=400, detail="Telegram not configured")

    bot = TelegramBot(telegram_config.bot_token, telegram_config.chat_id)

    # Test connection
    if bot.test_connection():
        # Send test message
        test_message = "✅ Burglary Alert System - Telegram connection successful!"
        if bot.send_message(test_message):
            return TelegramTestResponse(
                status="success",
                message="Connection successful, test message sent",
            )
        else:
            return TelegramTestResponse(
                status="partial",
                message="Bot connection OK but message send failed",
            )
    else:
        raise HTTPException(status_code=400, detail="Telegram connection failed")
