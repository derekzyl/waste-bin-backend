"""API routers for burglary alert system."""

from .alerts import router as alerts_router
from .auth import router as auth_router
from .devices import router as devices_router
from .images import router as images_router
from .telegram import router as telegram_router

__all__ = [
    "alerts_router",
    "auth_router",
    "images_router",
    "telegram_router",
    "devices_router",
]
