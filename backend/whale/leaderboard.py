"""Whale Leaderboard Engine.

Ranks tracked whales by various performance metrics:
ROI, win rate, PnL, volume.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import WhaleWallet

logger = logging.getLogger(__name__)

# Valid sort fields for leaderboard
SORT_FIELDS = {
    "roi": WhaleWallet.roi_pct,
    "pnl": WhaleWallet.total_pnl_usd,
    "volume": WhaleWallet.total_volume_usd,
    "win_rate": WhaleWallet.win_rate,
    "trades": WhaleWallet.num_trades,
}


async def get_leaderboard(
    session: AsyncSession,
    sort_by: str = "roi",
    limit: int = 50,
    offset: int = 0,
    active_only: bool = True,
) -> dict:
    """Generate the whale leaderboard ranked by the specified metric.

    Args:
        session: Database session.
        sort_by: Ranking metric — one of 'roi', 'pnl', 'volume', 'win_rate', 'trades'.
        limit: Maximum entries to return.
        offset: Pagination offset.
        active_only: If True, only include active wallets.

    Returns:
        Dict with 'entries' list, 'total' count, 'sort_by', and 'updated_at'.
    """
    sort_by = sort_by.lower()
    if sort_by not in SORT_FIELDS:
        sort_by = "roi"

    sort_column = SORT_FIELDS[sort_by]

    # Base query
    base = select(WhaleWallet)
    count_base = select(WhaleWallet)
    if active_only:
        base = base.where(WhaleWallet.is_active == True)
        count_base = count_base.where(WhaleWallet.is_active == True)

    # Count total
    from sqlalchemy import func
    count_result = await session.execute(
        select(func.count()).select_from(count_base.subquery())
    )
    total = count_result.scalar_one()

    # Fetch sorted page
    result = await session.execute(
        base.order_by(sort_column.desc()).offset(offset).limit(limit)
    )
    wallets = result.scalars().all()

    entries = []
    for rank_idx, wallet in enumerate(wallets, start=offset + 1):
        entries.append({
            "rank": rank_idx,
            "address": wallet.address,
            "label": wallet.label,
            "roi_pct": round(wallet.roi_pct, 2),
            "win_rate": round(wallet.win_rate, 3),
            "total_pnl_usd": round(wallet.total_pnl_usd, 2),
            "total_volume_usd": round(wallet.total_volume_usd, 2),
            "num_trades": wallet.num_trades,
            "num_markets": wallet.num_markets,
            "is_active": wallet.is_active,
        })

    logger.debug(
        "Leaderboard generated: %d entries, sorted by %s, total=%d",
        len(entries), sort_by, total,
    )

    return {
        "entries": entries,
        "total": total,
        "sort_by": sort_by,
        "updated_at": datetime.now(timezone.utc),
    }
