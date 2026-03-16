"""Whale API endpoints: leaderboard, profiles, positions, alerts, discovery."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.utils import get_current_user
from database import get_session
from models import User, WhalePosition, WhaleWallet

from .discovery import discover_top_traders, get_wallet_profile, sync_discovered_whales
from .leaderboard import get_leaderboard
from .schemas import (
    LeaderboardResponse,
    WhaleAlert,
    WhaleAlertListResponse,
    WhalePositionSchema,
    WhaleProfile,
)
from .tracker import scan_all_whales

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/whale", tags=["whale"])

# In-memory alert cache (would use Redis in production)
_recent_alerts: list[dict] = []
MAX_CACHED_ALERTS = 200


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def leaderboard(
    sort_by: str = Query("roi", description="Sort by: roi, pnl, volume, win_rate, trades"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    active_only: bool = Query(True),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get the whale leaderboard ranked by the specified metric."""
    return await get_leaderboard(
        session=session,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
        active_only=active_only,
    )


@router.get("/whale/{address}", response_model=WhaleProfile)
async def get_whale(
    address: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WhaleWallet:
    """Get a specific whale's profile by wallet address."""
    wallet = await get_wallet_profile(session, address)
    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Whale wallet not found: {address}",
        )
    return wallet


@router.get("/whale/{address}/positions", response_model=list[WhalePositionSchema])
async def get_whale_positions(
    address: str,
    open_only: bool = Query(True),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[WhalePosition]:
    """Get a whale's current positions."""
    wallet = await get_wallet_profile(session, address)
    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Whale wallet not found: {address}",
        )

    query = select(WhalePosition).where(WhalePosition.wallet_id == wallet.id)
    if open_only:
        query = query.where(WhalePosition.is_open == True)
    query = query.order_by(WhalePosition.opened_at.desc())

    result = await session.execute(query)
    return list(result.scalars().all())


@router.get("/alerts", response_model=WhaleAlertListResponse)
async def get_alerts(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get recent whale movement alerts.

    Returns cached alerts from the most recent scan.
    In production, this would be backed by Redis pub/sub.
    """
    # If no cached alerts, trigger a fresh scan
    if not _recent_alerts:
        try:
            alerts = await scan_all_whales(session)
            _update_alert_cache(alerts)
        except Exception as exc:
            logger.error("Alert scan failed: %s", exc)

    recent = _recent_alerts[:limit]
    return {
        "alerts": recent,
        "total": len(_recent_alerts),
    }


@router.post("/discover", status_code=status.HTTP_200_OK)
async def trigger_discovery(
    min_volume: float = Query(10_000, description="Minimum volume in USD"),
    min_trades: int = Query(20, description="Minimum number of trades"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Trigger whale discovery: find and sync profitable wallets.

    Queries Polymarket's leaderboard API and adds qualifying wallets
    to the tracked whale database.
    """
    discovered = await discover_top_traders(
        min_volume=min_volume,
        min_trades=min_trades,
    )

    if not discovered:
        return {"message": "No qualifying wallets found", "discovered": 0}

    summary = await sync_discovered_whales(session, discovered)
    return {
        "message": "Discovery complete",
        **summary,
    }


@router.post("/scan", status_code=status.HTTP_200_OK)
async def trigger_scan(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Trigger a manual whale position scan.

    Scans all active whale wallets for position changes and
    generates alerts for any detected moves.
    """
    alerts = await scan_all_whales(session)
    _update_alert_cache(alerts)

    return {
        "message": "Scan complete",
        "alerts_generated": len(alerts),
        "total_cached_alerts": len(_recent_alerts),
    }


def _update_alert_cache(new_alerts: list[dict]) -> None:
    """Add new alerts to the in-memory cache, maintaining max size."""
    global _recent_alerts
    _recent_alerts = (new_alerts + _recent_alerts)[:MAX_CACHED_ALERTS]
