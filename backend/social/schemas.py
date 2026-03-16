"""Pydantic v2 schemas for social endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ShareRequest(BaseModel):
    """Request to share a prediction or trade."""
    content_type: str = Field(pattern="^(prediction|trade|brag)$")
    content_id: uuid.UUID
    platform: str = Field(default="twitter", pattern="^(twitter|telegram|discord)$")
    message: Optional[str] = Field(default=None, max_length=280)


class ShareResponse(BaseModel):
    """Response after sharing content."""
    share_url: str
    platform: str
    content_type: str
    shared_at: datetime


class ReferralCode(BaseModel):
    """User's referral code."""
    code: str
    referral_url: str
    created_at: datetime


class ReferralStats(BaseModel):
    """Referral program statistics for a user."""
    referral_code: str
    total_signups: int
    total_earnings_credits: int
    total_earnings_usd: float
    recent_referrals: list[ReferralEntry]


class ReferralEntry(BaseModel):
    """Single referral record."""
    referee_username: str
    signed_up_at: datetime
    credits_earned: int


# Fix forward reference
ReferralStats.model_rebuild()


class BragRequest(BaseModel):
    """Request to generate a brag card."""
    trade_id: Optional[uuid.UUID] = None
    prediction_id: Optional[uuid.UUID] = None
    custom_message: Optional[str] = Field(default=None, max_length=200)


class BragCardData(BaseModel):
    """Generated brag card data."""
    card_id: str
    svg_content: str
    image_url: Optional[str] = None
    share_text: str
    stats: dict
    created_at: datetime
