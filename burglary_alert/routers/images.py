"""Images router - Updated for Cloudinary storage."""

from datetime import datetime
from typing import Optional

from database import get_db
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..models.image import Image, ImageSource
from ..models.telegram_config import TelegramConfig
from ..services.correlation import correlate_image_with_alert
from ..utils.auth import verify_device_api_key

router = APIRouter(prefix="/image", tags=["Images"])


class ImageUploadResponse(BaseModel):
    """Image upload response model."""

    status: str
    image_id: int
    correlated: bool
    alert_id: Optional[int] = None
    telegram_sent: bool


@router.post("/image", response_model=ImageUploadResponse)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Receive image directly from ESP32-CAM.
    Uploads to Cloudinary and correlates with alerts.
    """
    # Verify device API key
    api_key = request.headers.get("X-API-Key")
    if not verify_device_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    try:
        # Read image data
        image_data = await file.read()

        print(f"Received image: {len(image_data)} bytes")

        # Generate filename
        timestamp = datetime.utcnow()
        filename = f"capture_{int(timestamp.timestamp())}.jpg"

        # Upload to Cloudinary
        from ..utils.storage import storage

        image_url, thumbnail_url = storage.save_image(image_data, filename)

        # Create image record
        image = Image(
            timestamp=timestamp,
            image_path=image_url,  # Cloudinary URL
            thumbnail_path=thumbnail_url,  # Cloudinary thumbnail URL
            file_size=len(image_data),
            received_from=ImageSource.ESP32_CAM,
        )

        db.add(image)
        db.commit()
        db.refresh(image)

        print(f"Image saved to Cloudinary with ID: {image.id}")

        # Attempt correlation
        alert = correlate_image_with_alert(db, image)

        correlated = alert is not None
        alert_id = alert.id if alert else None

        # Forward to Telegram if configured
        telegram_sent = False
        telegram_config = (
            db.query(TelegramConfig).filter(TelegramConfig.active == True).first()
        )

        if telegram_config:
            try:
                from ..services.telegram_bot import send_image_to_telegram

                caption = "🚨 Intruder Alert!\n"
                caption += f"Time: {image.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"

                if correlated and alert:
                    caption += f"Confidence: {alert.detection_confidence * 100:.0f}%\n"
                    caption += "Sensors: "
                    sensors = []
                    if alert.pir_left:
                        sensors.append("Left")
                    if alert.pir_middle:
                        sensors.append("Middle")
                    if alert.pir_right:
                        sensors.append("Right")
                    caption += ", ".join(sensors)

                telegram_sent = send_image_to_telegram(
                    telegram_config.bot_token,
                    telegram_config.chat_id,
                    image_url,  # Send Cloudinary URL directly
                    caption,
                )
            except Exception as e:
                print(f"Telegram send error: {str(e)}")

        return ImageUploadResponse(
            status="success",
            image_id=image.id,
            correlated=correlated,
            alert_id=alert_id,
            telegram_sent=telegram_sent,
        )

    except Exception as e:
        print(f"Image upload error: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
