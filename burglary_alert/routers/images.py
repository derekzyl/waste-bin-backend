"""Images router."""

from datetime import datetime
from typing import Optional

from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..models.image import Image, ImageSource
from ..models.telegram_config import TelegramConfig
from ..services.correlation import correlate_image_with_alert
from ..services.telegram_bot import TelegramBot
from ..utils.auth import verify_device_api_key
from ..utils.storage import UPLOAD_DIR, generate_thumbnail, save_raw_image

router = APIRouter(prefix="/image", tags=["Images"])


class ImageUploadResponse(BaseModel):
    """Image upload response model."""

    status: str
    image_id: int
    correlated: bool
    alert_id: Optional[int] = None
    telegram_sent: bool


@router.post("/image", response_model=ImageUploadResponse)
async def receive_image(
    request: Request,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_device_api_key),
):
    """
    Receive image directly from ESP32-CAM.

    Accepts raw JPEG data in request body.
    Performs correlation with alerts and forwards to Telegram.

    Requires device API key authentication.
    """
    try:
        # Read raw image data
        image_data = await request.body()

        if not image_data or len(image_data) == 0:
            raise HTTPException(status_code=400, detail="No image data received")

        print(f"📸 Image received: {len(image_data)} bytes")

        # Save image
        timestamp = datetime.utcnow()
        filename, file_size = save_raw_image(image_data, timestamp)

        # Generate thumbnail
        thumbnail_filename = generate_thumbnail(filename)

        # Create image record
        new_image = Image(
            timestamp=timestamp,
            image_path=filename,
            thumbnail_path=thumbnail_filename,
            file_size=file_size,
            received_from=ImageSource.ESP32_CAM,
        )

        db.add(new_image)
        db.commit()
        db.refresh(new_image)

        print(f"✅ Image saved: ID={new_image.id}, File={filename}")

        # Correlate with alert
        correlated_alert = correlate_image_with_alert(new_image, db)

        # Forward to Telegram
        telegram_sent = False
        telegram_config = db.query(TelegramConfig).first()

        if telegram_config and telegram_config.active:
            bot = TelegramBot(telegram_config.bot_token, telegram_config.chat_id)
            image_path = UPLOAD_DIR / filename

            caption = (
                f"🚨 Intruder detected at {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            if correlated_alert:
                caption += f"\nConfidence: {correlated_alert.detection_confidence:.1%}"
                pir = correlated_alert.pir_sensors_triggered
                sensors = [k for k, v in pir.items() if v]
                if sensors:
                    caption += f"\nSensors: {', '.join(sensors)}"

            telegram_sent = bot.send_image(str(image_path), caption)

        return ImageUploadResponse(
            status="success",
            image_id=new_image.id,
            correlated=correlated_alert is not None,
            alert_id=correlated_alert.id if correlated_alert else None,
            telegram_sent=telegram_sent,
        )

    except Exception as e:
        db.rollback()
        print(f"❌ Error receiving image: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")
