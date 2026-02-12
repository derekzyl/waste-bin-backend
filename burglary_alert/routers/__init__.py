"""API routers for burglary alert system."""

from .alerts import router as alerts_router
from .auth import router as auth_router
from .images import router as images_router
from .telegram import router as telegram_router

__all__ = ["auth_router", "alerts_router", "images_router", "telegram_router"]
