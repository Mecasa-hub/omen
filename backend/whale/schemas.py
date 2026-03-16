"""Pydantic v2 schemas for whale tracking endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WhaleProfile(BaseModel):
    """Public profile of a tracked whale wallet."""
    id: uuid.UUID
    address: str
    label: Optional[str] = None
    total_volume_usd: float
    total_pnl_usd: float
    win_rate: float = Field(ge=0.0, le=1.0)
    roi_pct: float
    num_trades: int
    num_markets: int
    is_active: bool
    last_activity_at: Optional[datetime] = None
    discovered_at: datetime

    model_config = {"from_attributes": True}


class WhalePositionSchema(BaseModel):
    """A whale's position in a specific market."""
    id: uuid.UUID
    market_id: str
    market_question: Optional[str] = None
    token_id: str
    side: str
    size: float
    avg_price: float
    current_price: Optional[float] = None
    pnl_usd: Optional[float] = None
    is_open: bool
    opened_at: datetime
    closed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WhaleAlert(BaseModel):
    """Alert generated when a whale makes a significant move."""
    alert_id: str
    alert_type: str = Field(description="new_position, increase, decrease, exit")
    whale_address: str
    whale_label: Optional[str] = None
    market_id: str
    market_question: Optional[str] = None
    side: str
    size_change: float
    total_size: float
    price: float
    timestamp: datetime


class LeaderboardEntry(BaseModel):
    """Single entry in the whale leaderboard."""
    rank: int
    address: str
    label: Optional[str] = None
    roi_pct: float
    win_rate: float
    total_pnl_usd: float
    total_volume_usd: float
    num_trades: int
    num_markets: int
    is_active: bool


class LeaderboardResponse(BaseModel):
    """Full leaderboard response."""
    entries: list[LeaderboardEntry]
    total: int
    sort_by: str
    updated_at: datetime


class WhaleAlertListResponse(BaseModel):
    """List of recent whale alerts."""
    alerts: list[WhaleAlert]
    total: int
