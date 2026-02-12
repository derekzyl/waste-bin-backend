"""Authentication router."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..utils.auth import STATIC_PASSWORD, STATIC_USERNAME, create_jwt_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    """Login request model."""

    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response model."""

    access_token: str
    token_type: str


@router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest):
    """
    Simple static authentication endpoint.

    Validates username/password against environment variables,
    returns JWT token on success.
    """
    if (
        credentials.username == STATIC_USERNAME
        and credentials.password == STATIC_PASSWORD
    ):
        token = create_jwt_token({"sub": credentials.username})
        return LoginResponse(access_token=token, token_type="bearer")

    raise HTTPException(status_code=401, detail="Invalid credentials")
