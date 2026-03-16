"""OMEN — All SQLAlchemy ORM Models.

Tables: users, credit_transactions, predictions, trades,
whale_wallets, whale_positions, chat_messages, referrals.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey,
    Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database import Base


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(timezone.utc)


def _new_uuid() -> uuid.UUID:
    """Generate a new UUID4."""
    return uuid.uuid4()


# ════════════════════════════════════════════════════════════════
# User
# ════════════════════════════════════════════════════════════════
class User(Base):
    """Registered platform user."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid,
    )
    email: Mapped[str] = mapped_column(
        String(320), unique=True, nullable=False, index=True,
    )
    username: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True,
    )
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    credit_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    referral_code: Mapped[Optional[str]] = mapped_column(
        String(16), unique=True, nullable=True, index=True,
    )
    referred_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )
    polymarket_api_key: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    polymarket_api_secret: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    polymarket_passphrase: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    credit_transactions: Mapped[list["CreditTransaction"]] = relationship(
        back_populates="user", lazy="selectin",
    )
    trades: Mapped[list["Trade"]] = relationship(back_populates="user", lazy="selectin")
    predictions: Mapped[list["Prediction"]] = relationship(
        back_populates="user", lazy="selectin",
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="user", lazy="selectin",
    )
    referrals_made: Mapped[list["Referral"]] = relationship(
        back_populates="referrer", foreign_keys="Referral.referrer_id", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User {self.username}>"


# ════════════════════════════════════════════════════════════════
# Credit Transaction
# ════════════════════════════════════════════════════════════════
class TransactionType(str, enum.Enum):
    """Types of credit-balance mutations."""
    PURCHASE = "purchase"
    PREDICTION = "prediction"
    TRADE_FEE = "trade_fee"
    WIN_FEE = "win_fee"
    REFERRAL_BONUS = "referral_bonus"
    ADMIN_ADJUSTMENT = "admin_adjustment"


class CreditTransaction(Base):
    """Immutable ledger entry for every credit balance change."""

    __tablename__ = "credit_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True,
    )
    tx_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType), nullable=False,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    stripe_payment_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="credit_transactions")

    __table_args__ = (
        Index("ix_credit_tx_user_created", "user_id", "created_at"),
    )


# ════════════════════════════════════════════════════════════════
# Prediction
# ════════════════════════════════════════════════════════════════
class PredictionStatus(str, enum.Enum):
    """Lifecycle states of a prediction request."""
    PENDING = "pending"
    DEBATING = "debating"
    COMPLETED = "completed"
    FAILED = "failed"


class Prediction(Base):
    """Oracle prediction with debate transcript and verdict."""

    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True,
    )
    market_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[PredictionStatus] = mapped_column(
        Enum(PredictionStatus), default=PredictionStatus.PENDING,
    )
    verdict: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    debate_log: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    agent_votes: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    whale_alignment: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    user: Mapped["User"] = relationship(back_populates="predictions")


# ════════════════════════════════════════════════════════════════
# Trade
# ════════════════════════════════════════════════════════════════
class TradeStatus(str, enum.Enum):
    """Trade lifecycle states."""
    PENDING = "pending"
    PLACED = "placed"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


class TradeSide(str, enum.Enum):
    """Trade direction."""
    BUY = "buy"
    SELL = "sell"


class Trade(Base):
    """Record of every trade placed through OMEN."""

    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True,
    )
    market_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    token_id: Mapped[str] = mapped_column(String(256), nullable=False)
    side: Mapped[TradeSide] = mapped_column(Enum(TradeSide), nullable=False)
    amount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    size: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[TradeStatus] = mapped_column(
        Enum(TradeStatus), default=TradeStatus.PENDING,
    )
    order_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    fee_usd: Mapped[float] = mapped_column(Float, default=0.0)
    pnl_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_copy_trade: Mapped[bool] = mapped_column(Boolean, default=False)
    copy_source_wallet: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    prediction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("predictions.id"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="trades")

    __table_args__ = (
        Index("ix_trade_user_created", "user_id", "created_at"),
    )


# ════════════════════════════════════════════════════════════════
# Whale Wallet & Position
# ════════════════════════════════════════════════════════════════
class WhaleWallet(Base):
    """Tracked whale wallet with aggregated performance metrics."""

    __tablename__ = "whale_wallets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid,
    )
    address: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True,
    )
    label: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    total_volume_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_pnl_usd: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    roi_pct: Mapped[float] = mapped_column(Float, default=0.0)
    num_trades: Mapped[int] = mapped_column(Integer, default=0)
    num_markets: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    positions: Mapped[list["WhalePosition"]] = relationship(
        back_populates="wallet", lazy="selectin",
    )


class WhalePosition(Base):
    """Snapshot of a whale's position in a specific market."""

    __tablename__ = "whale_positions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid,
    )
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("whale_wallets.id"), nullable=False, index=True,
    )
    market_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    market_question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_id: Mapped[str] = mapped_column(String(256), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    size: Mapped[float] = mapped_column(Float, nullable=False)
    avg_price: Mapped[float] = mapped_column(Float, nullable=False)
    current_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    wallet: Mapped["WhaleWallet"] = relationship(back_populates="positions")

    __table_args__ = (
        Index("ix_whale_pos_wallet_market", "wallet_id", "market_id"),
    )


# ════════════════════════════════════════════════════════════════
# Chat Message
# ════════════════════════════════════════════════════════════════
class ChatRole(str, enum.Enum):
    """Message author role."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(Base):
    """Per-user chat history with the OMEN AI assistant."""

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True,
    )
    role: Mapped[ChatRole] = mapped_column(Enum(ChatRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="chat_messages")

    __table_args__ = (
        Index("ix_chat_user_created", "user_id", "created_at"),
    )


# ════════════════════════════════════════════════════════════════
# Referral
# ════════════════════════════════════════════════════════════════

class ReferralStatus(str, enum.Enum):
    """Referral relationship states."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"

class Referral(Base):
    """Tracks which user referred whom and total bonus earned."""

    __tablename__ = "referrals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid,
    )
    referrer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True,
    )
    referee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True,
    )
    referral_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default=ReferralStatus.ACTIVE.value, nullable=False)
    total_earned_credits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    referrer: Mapped["User"] = relationship(
        back_populates="referrals_made", foreign_keys=[referrer_id],
    )

    __table_args__ = (
        UniqueConstraint("referrer_id", "referee_id", name="uq_referral_pair"),
    )
