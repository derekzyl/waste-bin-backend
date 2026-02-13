print("Checking imports...")
try:
    from burglary_alert.utils import CloudinaryStorage, storage

    print("✅ burglary_alert.utils import successful")
except ImportError as e:
    print(f"❌ burglary_alert.utils import failed: {e}")

try:
    from burglary_alert.routers import images

    print("✅ burglary_alert.routers.images import successful")
except ImportError as e:
    print(f"❌ burglary_alert.routers.images import failed: {e}")

try:
    from burglary_alert.services import correlation

    print("✅ burglary_alert.services.correlation import successful")
except ImportError as e:
    print(f"❌ burglary_alert.services.correlation import failed: {e}")

try:
    from burglary_alert.models import image

    print("✅ burglary_alert.models.image import successful")
except ImportError as e:
    print(f"❌ burglary_alert.models.image import failed: {e}")
