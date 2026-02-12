"""File storage utilities for burglary alert system."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

from fastapi import UploadFile
from PIL import Image

UPLOAD_DIR = Path("backend/uploads/burglary")
MAX_IMAGE_SIZE_MB = 5
THUMBNAIL_SIZE = (200, 150)


def ensure_upload_dir():
    """Ensure upload directory exists."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def save_uploaded_image(
    file: UploadFile, timestamp: Optional[datetime] = None
) -> Tuple[str, int]:
    """
    Save uploaded image to filesystem.

    Args:
        file: Uploaded file from FastAPI
        timestamp: Optional timestamp for filename

    Returns:
        Tuple of (filename, file_size_bytes)
    """
    ensure_upload_dir()

    if timestamp is None:
        timestamp = datetime.utcnow()

    # Generate unique filename
    filename = f"img_{timestamp.strftime('%Y%m%d_%H%M%S')}_{timestamp.microsecond}.jpg"
    file_path = UPLOAD_DIR / filename

    # Save file
    file_size = 0
    with open(file_path, "wb") as f:
        content = file.file.read()
        file_size = len(content)
        f.write(content)

    return filename, file_size


def save_raw_image(
    image_data: bytes, timestamp: Optional[datetime] = None
) -> Tuple[str, int]:
    """
    Save raw image bytes to filesystem (for ESP32-CAM direct upload).

    Args:
        image_data: Raw JPEG bytes
        timestamp: Optional timestamp for filename

    Returns:
        Tuple of (filename, file_size_bytes)
    """
    ensure_upload_dir()

    if timestamp is None:
        timestamp = datetime.utcnow()

    # Generate unique filename
    filename = f"img_{timestamp.strftime('%Y%m%d_%H%M%S')}_{timestamp.microsecond}.jpg"
    file_path = UPLOAD_DIR / filename

    # Save file
    with open(file_path, "wb") as f:
        f.write(image_data)

    return filename, len(image_data)


def generate_thumbnail(
    image_filename: str, size: Tuple[int, int] = THUMBNAIL_SIZE
) -> Optional[str]:
    """
    Generate thumbnail for an image.

    Args:
        image_filename: Original image filename
        size: Thumbnail size (width, height)

    Returns:
        Thumbnail filename or None if failed
    """
    try:
        image_path = UPLOAD_DIR / image_filename
        if not image_path.exists():
            return None

        # Generate thumbnail filename
        thumb_filename = f"thumb_{image_filename}"
        thumb_path = UPLOAD_DIR / thumb_filename

        # Create thumbnail
        with Image.open(image_path) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(thumb_path, "JPEG", quality=85)

        return thumb_filename
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return None


def cleanup_old_files(days: int = 30):
    """
    Delete files older than specified days.

    Args:
        days: Number of days to keep files
    """
    ensure_upload_dir()

    cutoff_date = datetime.utcnow() - timedelta(days=days)
    deleted_count = 0

    for file_path in UPLOAD_DIR.iterdir():
        if file_path.is_file():
            file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if file_mtime < cutoff_date:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")

    print(f"Cleaned up {deleted_count} old files")
    return deleted_count
