"""Auth API endpoints: register, login, profile, token refresh."""

from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models import Referral, User

from .schemas import TokenResponse, UserCreate, UserLogin, UserResponse
from .utils import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def _generate_referral_code() -> str:
    """Generate a URL-safe 8-character referral code."""
    return secrets.token_urlsafe(6)[:8].upper()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> User:
    """Create a new user with hashed password and unique referral code."""
    # Check for existing email or username
    existing = await session.execute(
        select(User).where(or_(User.email == body.email, User.username == body.username))
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or username already registered",
        )

    # Validate referral code if provided
    referrer = None
    if body.referral_code:
        ref_result = await session.execute(
            select(User).where(User.referral_code == body.referral_code.upper())
        )
        referrer = ref_result.scalar_one_or_none()
        if referrer is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid referral code",
            )

    # Create user
    user = User(
        email=body.email,
        username=body.username,
        hashed_password=hash_password(body.password),
        referral_code=_generate_referral_code(),
        referred_by=referrer.id if referrer else None,
    )
    session.add(user)
    await session.flush()  # Get user.id before creating referral

    # Create referral record if referred
    if referrer:
        ref = Referral(
            referrer_id=referrer.id,
            referee_id=user.id,
            referral_code=body.referral_code.upper(),
        )
        session.add(ref)

    await session.commit()
    await session.refresh(user)
    logger.info("New user registered: %s (%s)", user.username, user.email)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    body: UserLogin,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Authenticate user and return JWT token pair."""
    # Accept either email or username
    result = await session.execute(
        select(User).where(
            or_(User.email == body.login, User.username == body.login.lower())
        )
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated",
        )

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    logger.info("User logged in: %s", user.username)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_expire_minutes * 60,
    }


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return the current authenticated user's profile."""
    return current_user


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: dict,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Exchange a valid refresh token for a new access/refresh token pair."""
    token = body.get("refresh_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="refresh_token required",
        )

    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type — refresh token required",
        )

    import uuid as _uuid
    user_id = _uuid.UUID(payload["sub"])
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    new_access = create_access_token(user.id)
    new_refresh = create_refresh_token(user.id)

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_expire_minutes * 60,
    }
