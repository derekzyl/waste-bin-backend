"""Authentication utilities for burglary alert system."""

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Header, HTTPException
from jose import JWTError, jwt

# Configuration
SECRET_KEY = os.getenv("BURGLARY_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

STATIC_USERNAME = os.getenv("BURGLARY_USERNAME", "admin")
STATIC_PASSWORD = os.getenv("BURGLARY_PASSWORD", "admin123")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "esp32_device_key_xyz789")


def create_jwt_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_jwt_token(token: str) -> dict:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")


def verify_device_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> bool:
    """Verify device API key from header."""
    if x_api_key != DEVICE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


def get_current_user(authorization: str = Header(..., alias="Authorization")) -> dict:
    """Get current user from JWT token in Authorization header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.replace("Bearer ", "")
    payload = verify_jwt_token(token)

    username = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    return {"username": username}
