"""
Background task for cleaning up old images from Cloudinary.
Run this as a scheduled task (cron job or systemd timer).
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from burglary_alert.utils.storage import storage
from database import get_db


def cleanup_old_images():
    """Clean up images older than retention period."""
    print("Starting image cleanup task...")

    db = next(get_db())

    try:
        deleted_count = storage.cleanup_old_images(db)
        print(f"Cleanup complete: {deleted_count} images deleted")
    except Exception as e:
        print(f"Cleanup error: {str(e)}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    cleanup_old_images()
