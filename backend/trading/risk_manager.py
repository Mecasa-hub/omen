"""Risk Management Engine.

Enforces position limits, daily loss limits, and maximum exposure
checks before any trade is executed.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Trade, TradeStatus

logger = logging.getLogger(__name__)

# Risk limits (configurable per user tier in production)
MAX_SINGLE_TRADE_USD = 500.0
MAX_DAILY_VOLUME_USD = 5_000.0
MAX_DAILY_LOSS_USD = 1_000.0
MAX_OPEN_POSITIONS = 20
MAX_POSITION_PER_MARKET_USD = 1_000.0


@dataclass
class RiskCheck:
    """Result of a risk check."""
    passed: bool
    reason: str = ""
    current_value: float = 0.0
    limit_value: float = 0.0


async def check_risk_limits(
    session: AsyncSession,
    user_id: uuid.UUID,
    market_id: str,
    amount_usd: float,
) -> RiskCheck:
    """Run all risk checks before allowing a trade.

    Checks:
    1. Single trade size limit
    2. Daily volume limit
    3. Daily loss limit
    4. Open positions limit
    5. Per-market exposure limit

    Returns:
        RiskCheck with passed=True if all checks pass.
    """
    # 1. Single trade size
    if amount_usd > MAX_SINGLE_TRADE_USD:
        return RiskCheck(
            passed=False,
            reason=f"Trade amount ${amount_usd:.2f} exceeds max ${MAX_SINGLE_TRADE_USD:.2f}",
            current_value=amount_usd,
            limit_value=MAX_SINGLE_TRADE_USD,
        )

    # 2. Daily volume limit
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    daily_volume_result = await session.execute(
        select(func.coalesce(func.sum(Trade.amount_usd), 0.0))
        .where(
            Trade.user_id == user_id,
            Trade.created_at >= today_start,
            Trade.status.in_([TradeStatus.PLACED, TradeStatus.FILLED, TradeStatus.PARTIALLY_FILLED]),
        )
    )
    daily_volume = float(daily_volume_result.scalar_one())

    if daily_volume + amount_usd > MAX_DAILY_VOLUME_USD:
        return RiskCheck(
            passed=False,
            reason=f"Daily volume ${daily_volume + amount_usd:.2f} would exceed limit ${MAX_DAILY_VOLUME_USD:.2f}",
            current_value=daily_volume,
            limit_value=MAX_DAILY_VOLUME_USD,
        )

    # 3. Daily loss limit
    daily_loss_result = await session.execute(
        select(func.coalesce(func.sum(Trade.pnl_usd), 0.0))
        .where(
            Trade.user_id == user_id,
            Trade.created_at >= today_start,
            Trade.pnl_usd < 0,
        )
    )
    daily_loss = abs(float(daily_loss_result.scalar_one()))

    if daily_loss >= MAX_DAILY_LOSS_USD:
        return RiskCheck(
            passed=False,
            reason=f"Daily loss ${daily_loss:.2f} has reached limit ${MAX_DAILY_LOSS_USD:.2f}",
            current_value=daily_loss,
            limit_value=MAX_DAILY_LOSS_USD,
        )

    # 4. Open positions limit
    open_positions_result = await session.execute(
        select(func.count())
        .select_from(Trade)
        .where(
            Trade.user_id == user_id,
            Trade.status.in_([TradeStatus.PLACED, TradeStatus.FILLED, TradeStatus.PARTIALLY_FILLED]),
        )
    )
    open_positions = int(open_positions_result.scalar_one())

    if open_positions >= MAX_OPEN_POSITIONS:
        return RiskCheck(
            passed=False,
            reason=f"Open positions ({open_positions}) at limit ({MAX_OPEN_POSITIONS})",
            current_value=float(open_positions),
            limit_value=float(MAX_OPEN_POSITIONS),
        )

    # 5. Per-market exposure limit
    market_exposure_result = await session.execute(
        select(func.coalesce(func.sum(Trade.amount_usd), 0.0))
        .where(
            Trade.user_id == user_id,
            Trade.market_id == market_id,
            Trade.status.in_([TradeStatus.PLACED, TradeStatus.FILLED, TradeStatus.PARTIALLY_FILLED]),
        )
    )
    market_exposure = float(market_exposure_result.scalar_one())

    if market_exposure + amount_usd > MAX_POSITION_PER_MARKET_USD:
        return RiskCheck(
            passed=False,
            reason=f"Market exposure ${market_exposure + amount_usd:.2f} would exceed ${MAX_POSITION_PER_MARKET_USD:.2f}",
            current_value=market_exposure,
            limit_value=MAX_POSITION_PER_MARKET_USD,
        )

    logger.debug(
        "Risk check passed: user=%s market=%s amount=$%.2f (daily_vol=$%.2f, daily_loss=$%.2f, open=%d)",
        user_id, market_id[:20], amount_usd, daily_volume, daily_loss, open_positions,
    )

    return RiskCheck(passed=True, reason="All risk checks passed")
