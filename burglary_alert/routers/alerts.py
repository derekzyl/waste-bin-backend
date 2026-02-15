"""Alerts router."""

from datetime import datetime, timezone
from typing import List, Optional

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..models.alert import Alert
from ..utils.auth import get_current_user, verify_device_api_key

router = APIRouter(prefix="/alert", tags=["Alerts"])


class AlertCreate(BaseModel):
    """Alert creation model."""

    timestamp: int  # Unix timestamp in milliseconds
    detection_confidence: float
    pir_left: bool
    pir_middle: bool
    pir_right: bool
    network_status: str  # "online" or "offline"


class AlertResponse(BaseModel):
    """Alert response model."""

    id: int
    timestamp: str
    alert_type: str
    detection_confidence: float
    pir_sensors_triggered: dict
    network_status: str
    image_id: Optional[int]
    correlated: bool
    image_url: Optional[str]


class SystemStatusResponse(BaseModel):
    """System status response model."""

    status: str
    total_alerts: int
    alerts_today: int
    last_alert: Optional[str]


def _format_utc_iso(dt: Optional[datetime]) -> str:
    """Format datetime as ISO 8601 with Z (UTC) for API responses."""
    if not dt:
        return ""
    # Ensure we have a UTC-aware moment, then output with Z
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


@router.post("/alert")
async def receive_alert(
    alert_data: AlertCreate,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_device_api_key),
):
    """
    Receive motion alert metadata from ESP32 main.

    Requires device API key authentication.
    """
    try:
        # Interpret epoch as UTC and store as naive UTC for DB compatibility
        timestamp = datetime.fromtimestamp(
            alert_data.timestamp / 1000.0, tz=timezone.utc
        ).replace(tzinfo=None)

        # Create PIR sensors JSON
        pir_sensors = {
            "left": alert_data.pir_left,
            "middle": alert_data.pir_middle,
            "right": alert_data.pir_right,
        }

        # Create new alert
        new_alert = Alert(
            timestamp=timestamp,
            alert_type="motion",
            detection_confidence=alert_data.detection_confidence,
            pir_sensors_triggered=pir_sensors,
            network_status=alert_data.network_status,
        )

        db.add(new_alert)
        db.commit()
        db.refresh(new_alert)

        print(
            f"📥 Alert received: ID={new_alert.id}, Confidence={alert_data.detection_confidence:.2f}"
        )

    except Exception as e:
        db.rollback()
        print(f"❌ Error receiving alert: {e}")
        raise HTTPException(status_code=500, detail=f"Error recording alert: {str(e)}")

    # Send Telegram notification if configured (same flow as backend)
    try:
        from ..models.telegram_config import TelegramConfig
        from ..services.telegram_bot import send_message_to_telegram

        telegram_config = db.query(TelegramConfig).filter(TelegramConfig.active).first()
        if telegram_config:
            timestamp_str = timestamp.strftime("%H:%M:%S")
            msg = (
                f"🚨 <b>INTRUDER ALERT!</b>\n"
                f"🕒 Time: {timestamp_str}\n"
                f"📊 Confidence: {alert_data.detection_confidence * 100:.0f}%\n"
                f"📡 Status: {alert_data.network_status}\n\n"
                f"<i>Image may follow if available...</i>"
            )
            send_message_to_telegram(
                telegram_config.bot_token, telegram_config.chat_id, msg
            )
            print("✓ Telegram alert sent")
    except Exception as e:
        print(f"⚠️ Failed to send Telegram alert: {e}")

    return {
        "status": "success",
        "alert_id": new_alert.id,
        "message": "Alert recorded successfully",
    }


@router.get("/feeds", response_model=List[AlertResponse])
async def get_alerts(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    Get paginated alert feed with images.

    Requires JWT authentication.
    """
    alerts = (
        db
        .query(Alert)
        .order_by(Alert.timestamp.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return [
        AlertResponse(
            id=alert.id,
            timestamp=_format_utc_iso(alert.timestamp),
            alert_type=alert.alert_type,
            detection_confidence=alert.detection_confidence,
            pir_sensors_triggered=alert.pir_sensors_triggered,
            network_status=alert.network_status,
            image_id=alert.image_id,
            correlated=alert.correlated,
            image_url=alert.image.image_path if alert.image else None,
        )
        for alert in alerts
    ]


@router.get("/feeds/{alert_id}", response_model=AlertResponse)
async def get_alert_by_id(
    alert_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    Get specific alert details.

    Requires JWT authentication.
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return AlertResponse(
        id=alert.id,
        timestamp=_format_utc_iso(alert.timestamp),
        alert_type=alert.alert_type,
        detection_confidence=alert.detection_confidence,
        pir_sensors_triggered=alert.pir_sensors_triggered,
        network_status=alert.network_status,
        image_id=alert.image_id,
        correlated=alert.correlated,
        image_url=alert.image.image_path if alert.image else None,
    )


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    """
    Get system health and device status.

    Requires JWT authentication.
    """
    # Get total alerts
    total_alerts = db.query(Alert).count()

    # Get alerts today
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    alerts_today = db.query(Alert).filter(Alert.timestamp >= today_start).count()

    # Get last alert
    last_alert = db.query(Alert).order_by(Alert.timestamp.desc()).first()
    last_alert_time = _format_utc_iso(last_alert.timestamp) if last_alert else None

    return SystemStatusResponse(
        status="healthy",
        total_alerts=total_alerts,
        alerts_today=alerts_today,
        last_alert=last_alert_time,
    )
