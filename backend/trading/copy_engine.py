"""Copy Trading Engine.

Mirrors whale positions with user-configurable settings.
Monitors whale alerts and automatically executes corresponding
trades for users who have active copy sessions.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Trade, User

from .executor import place_order
from .risk_manager import check_risk_limits

logger = logging.getLogger(__name__)

# In-memory copy session store (would use Redis in production)
_active_sessions: dict[str, dict] = {}  # key: "{user_id}:{whale_address}"


async def start_copy_session(
    session: AsyncSession,
    user: User,
    whale_address: str,
    max_trade_usd: float = 50.0,
    copy_percentage: float = 0.1,
    stop_loss_pct: float = 0.5,
    auto_exit: bool = True,
    markets_whitelist: Optional[list[str]] = None,
    markets_blacklist: Optional[list[str]] = None,
) -> dict:
    """Start a copy-trading session for a user following a whale.

    Args:
        session: Database session.
        user: User starting the copy session.
        whale_address: Whale wallet address to mirror.
        max_trade_usd: Maximum USD per copied trade.
        copy_percentage: Fraction of whale's position size to mirror.
        stop_loss_pct: Stop loss as fraction of trade amount.
        auto_exit: Whether to auto-exit when whale exits.
        markets_whitelist: Only copy trades in these markets.
        markets_blacklist: Never copy trades in these markets.

    Returns:
        Session status dict.
    """
    session_key = f"{user.id}:{whale_address.lower()}"

    if session_key in _active_sessions:
        return {
            "status": "already_active",
            "message": f"Already copying {whale_address[:10]}...",
            "whale_address": whale_address,
        }

    copy_config = {
        "user_id": str(user.id),
        "username": user.username,
        "whale_address": whale_address.lower(),
        "max_trade_usd": max_trade_usd,
        "copy_percentage": copy_percentage,
        "stop_loss_pct": stop_loss_pct,
        "auto_exit": auto_exit,
        "markets_whitelist": [m.lower() for m in (markets_whitelist or [])],
        "markets_blacklist": [m.lower() for m in (markets_blacklist or [])],
        "is_active": True,
        "trades_executed": 0,
        "total_pnl_usd": 0.0,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    _active_sessions[session_key] = copy_config

    logger.info(
        "Copy session started: user=%s whale=%s max=$%.2f pct=%.0f%%",
        user.username, whale_address[:10], max_trade_usd, copy_percentage * 100,
    )

    return {
        "status": "active",
        "message": f"Now copying {whale_address[:10]}...",
        "whale_address": whale_address,
        "config": copy_config,
    }


async def stop_copy_session(
    user: User,
    whale_address: str,
) -> dict:
    """Stop an active copy-trading session."""
    session_key = f"{user.id}:{whale_address.lower()}"

    if session_key not in _active_sessions:
        return {
            "status": "not_found",
            "message": f"No active copy session for {whale_address[:10]}...",
        }

    config = _active_sessions.pop(session_key)
    logger.info(
        "Copy session stopped: user=%s whale=%s trades=%d pnl=$%.2f",
        user.username, whale_address[:10],
        config["trades_executed"], config["total_pnl_usd"],
    )

    return {
        "status": "stopped",
        "message": f"Stopped copying {whale_address[:10]}...",
        "trades_executed": config["trades_executed"],
        "total_pnl_usd": config["total_pnl_usd"],
    }


async def process_whale_alert(
    db_session: AsyncSession,
    alert: dict,
) -> list[dict]:
    """Process a whale alert and execute copy trades for all followers.

    Called by the whale tracker when a position change is detected.
    Iterates through all active copy sessions for this whale and
    executes corresponding trades.

    Args:
        db_session: Database session.
        alert: Whale alert dict from tracker.

    Returns:
        List of executed trade summaries.
    """
    whale_address = alert.get("whale_address", "").lower()
    alert_type = alert.get("alert_type", "")
    market_id = alert.get("market_id", "")
    side = alert.get("side", "YES")
    size_change = abs(alert.get("size_change", 0))
    price = alert.get("price", 0.5)

    executed_trades = []

    # Find all active copy sessions for this whale
    for session_key, config in list(_active_sessions.items()):
        if config["whale_address"] != whale_address:
            continue
        if not config["is_active"]:
            continue

        # Check market whitelist/blacklist
        if config["markets_whitelist"] and market_id.lower() not in config["markets_whitelist"]:
            continue
        if config["markets_blacklist"] and market_id.lower() in config["markets_blacklist"]:
            continue

        user_id = uuid.UUID(config["user_id"])

        # Determine trade action based on alert type
        if alert_type in ("new_position", "increase"):
            trade_side = "buy"
        elif alert_type == "exit" and config["auto_exit"]:
            trade_side = "sell"
        elif alert_type == "decrease":
            trade_side = "sell"
        else:
            continue

        # Calculate copy trade amount
        copy_amount = min(
            size_change * price * config["copy_percentage"],
            config["max_trade_usd"],
        )

        if copy_amount < 1.0:  # Minimum trade size
            continue

        # Run risk checks
        risk = await check_risk_limits(db_session, user_id, market_id, copy_amount)
        if not risk.passed:
            logger.warning(
                "Copy trade blocked by risk: user=%s reason=%s",
                config["username"], risk.reason,
            )
            continue

        # Get user from DB
        from sqlalchemy import select as sa_select
        from models import User as UserModel
        user_result = await db_session.execute(
            sa_select(UserModel).where(UserModel.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            continue

        try:
            trade = await place_order(
                session=db_session,
                user=user,
                market_id=market_id,
                token_id=alert.get("token_id", market_id),
                side=trade_side,
                amount_usd=copy_amount,
                price=price,
                is_copy_trade=True,
                copy_source_wallet=whale_address,
            )

            config["trades_executed"] += 1
            executed_trades.append({
                "user": config["username"],
                "trade_id": str(trade.id),
                "side": trade_side,
                "amount_usd": copy_amount,
                "status": trade.status.value,
            })

            logger.info(
                "Copy trade executed: user=%s whale=%s market=%s side=%s amount=$%.2f",
                config["username"], whale_address[:10], market_id[:20], trade_side, copy_amount,
            )
        except Exception as exc:
            logger.error(
                "Copy trade failed: user=%s whale=%s error=%s",
                config["username"], whale_address[:10], exc,
            )

    if executed_trades:
        await db_session.commit()

    return executed_trades


def get_user_copy_sessions(user_id: uuid.UUID) -> list[dict]:
    """Get all active copy sessions for a user."""
    sessions = []
    for session_key, config in _active_sessions.items():
        if config["user_id"] == str(user_id):
            sessions.append(config)
    return sessions
