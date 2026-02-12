"""
Cloudinary storage utility for image uploads.
Images are automatically deleted after configured retention period (default: 24 hours).
Stored in dedicated folder to avoid interference with other projects.
"""

import os
from datetime import datetime, timedelta
from typing import Tuple

import cloudinary
import cloudinary.uploader


class CloudinaryStorage:
    def __init__(self):
        """Initialize Cloudinary with environment variables."""
        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True,
        )

        # Use dedicated folder for this project (isolated from other projects)
        self.folder = os.getenv("CLOUDINARY_FOLDER", "burglary_alerts")
        self.retention_hours = int(os.getenv("IMAGE_RETENTION_HOURS", "24"))

        print(
            f"📁 Cloudinary initialized: folder='{self.folder}', retention={self.retention_hours}h"
        )

    def save_image(self, image_data: bytes, filename: str) -> Tuple[str, str]:
        """
        Upload image to Cloudinary.

        Args:
            image_data: Raw JPEG image bytes
            filename: Desired filename (will be sanitized)

        Returns:
            Tuple of (full_image_url, thumbnail_url)
        """
        try:
            # Generate a unique public_id
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            public_id = f"{self.folder}/{timestamp}_{filename.replace('.jpg', '')}"

            # Upload full-size image
            result = cloudinary.uploader.upload(
                image_data,
                public_id=public_id,
                folder=self.folder,
                resource_type="image",
                format="jpg",
                # Add timestamp to metadata for cleanup
                context=f"upload_time={datetime.utcnow().isoformat()}",
            )

            full_url = result["secure_url"]

            # Generate thumbnail URL (200x150)
            thumbnail_url = cloudinary.CloudinaryImage(result["public_id"]).build_url(
                width=200,
                height=150,
                crop="fill",
                gravity="center",
                quality="auto",
                fetch_format="auto",
            )

            print(f"📸 Image uploaded to Cloudinary: {public_id}")
            print(f"🔗 Full URL: {full_url}")

            return full_url, thumbnail_url

        except Exception as e:
            print(f"❌ Cloudinary upload error: {str(e)}")
            raise

    def delete_image(self, image_url: str) -> bool:
        """
        Delete an image from Cloudinary.

        Args:
            image_url: Full Cloudinary URL

        Returns:
            True if deleted successfully
        """
        try:
            # Extract public_id from URL
            # URL format: https://res.cloudinary.com/{cloud_name}/image/upload/{public_id}.jpg
            parts = image_url.split("/")
            if "upload" in parts:
                upload_idx = parts.index("upload")
                public_id_with_ext = "/".join(parts[upload_idx + 1 :])
                public_id = public_id_with_ext.rsplit(".", 1)[0]  # Remove extension

                result = cloudinary.uploader.destroy(public_id)

                if result.get("result") == "ok":
                    print(f"🗑️  Image deleted from Cloudinary: {public_id}")
                    return True
                else:
                    print(f"⚠️  Cloudinary delete failed: {result}")
                    return False
            else:
                print(f"❌ Invalid Cloudinary URL format: {image_url}")
                return False

        except Exception as e:
            print(f"❌ Cloudinary delete error: {str(e)}")
            return False

    def cleanup_old_images(self, db_session):
        """
        Delete images older than retention period from both Cloudinary and database.
        Called automatically by daily background task.

        Args:
            db_session: SQLAlchemy database session
        """
        from ..models.image import Image

        cutoff_time = datetime.utcnow() - timedelta(hours=self.retention_hours)

        print(
            f"🔍 Checking for images older than {cutoff_time} ({self.retention_hours}h ago)"
        )

        # Find old images
        old_images = db_session.query(Image).filter(Image.timestamp < cutoff_time).all()

        if not old_images:
            print("✅ No old images to clean up")
            return 0

        deleted_count = 0

        for image in old_images:
            try:
                # Delete from Cloudinary
                if self.delete_image(image.image_path):
                    # Delete from database
                    db_session.delete(image)
                    deleted_count += 1
            except Exception as e:
                print(f"❌ Error deleting image {image.id}: {str(e)}")
                continue

        if deleted_count > 0:
            db_session.commit()
            print(f"✅ Cleaned up {deleted_count} old images from {self.folder}/")

        return deleted_count


# Global storage instance
storage = CloudinaryStorage()
