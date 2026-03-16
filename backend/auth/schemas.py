"""Pydantic v2 schemas for authentication endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    """Registration payload."""
    email: EmailStr
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)
    referral_code: Optional[str] = Field(default=None, max_length=16)

    @field_validator("username")
    @classmethod
    def username_lowercase(cls, v: str) -> str:
        """Normalize username to lowercase."""
        return v.lower()


class UserLogin(BaseModel):
    """Login payload — accepts email or username."""
    login: str = Field(description="Email or username")
    password: str


class UserResponse(BaseModel):
    """Public user representation returned from API."""
    id: uuid.UUID
    email: str
    username: str
    is_active: bool
    credit_balance: int
    referral_code: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """JWT token pair returned after login / refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token TTL in seconds")


class TokenPayload(BaseModel):
    """Decoded JWT claims."""
    sub: str
    exp: int
    type: str = "access"
