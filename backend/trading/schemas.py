"""Pydantic v2 schemas for trading endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TradeRequest(BaseModel):
    """Request to place a trade on Polymarket."""
    market_id: str = Field(description="Polymarket market/condition ID")
    token_id: str = Field(description="Outcome token ID")
    side: str = Field(pattern="^(buy|sell)$", description="buy or sell")
    amount_usd: float = Field(gt=0, le=10000, description="Trade amount in USD")
    price: Optional[float] = Field(default=None, ge=0.01, le=0.99, description="Limit price (None for market)")
    prediction_id: Optional[uuid.UUID] = Field(default=None, description="Link to prediction that triggered this")


class TradeResponse(BaseModel):
    """Response after placing a trade."""
    id: uuid.UUID
    market_id: str
    token_id: str
    side: str
    amount_usd: float
    price: float
    size: float
    status: str
    order_id: Optional[str] = None
    fee_usd: float
    is_copy_trade: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class Position(BaseModel):
    """Current open position."""
    id: uuid.UUID
    market_id: str
    token_id: str
    side: str
    size: float
    avg_price: float
    current_price: Optional[float] = None
    pnl_usd: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CopyTradeConfig(BaseModel):
    """Configuration for copy-trading a whale."""
    whale_address: str = Field(description="Whale wallet address to copy")
    max_trade_usd: float = Field(default=50.0, gt=0, le=1000, description="Max USD per copied trade")
    copy_percentage: float = Field(default=0.1, gt=0, le=1.0, description="Fraction of whale's position to mirror")
    stop_loss_pct: float = Field(default=0.5, ge=0.1, le=1.0, description="Stop loss as fraction of trade")
    auto_exit: bool = Field(default=True, description="Auto-exit when whale exits")
    markets_whitelist: Optional[list[str]] = Field(default=None, description="Only copy these market IDs")
    markets_blacklist: Optional[list[str]] = Field(default=None, description="Never copy these market IDs")


class CopyTradeStatus(BaseModel):
    """Status of an active copy-trade session."""
    whale_address: str
    is_active: bool
    config: CopyTradeConfig
    trades_executed: int
    total_pnl_usd: float
    started_at: datetime


class TradeHistoryResponse(BaseModel):
    """Paginated trade history."""
    trades: list[TradeResponse]
    total: int
    page: int
    page_size: int
