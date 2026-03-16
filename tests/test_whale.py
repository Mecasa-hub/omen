"""OMEN — Whale Tracker Module Tests.

Covers leaderboard, whale profile, positions, alerts,
whale discovery, and leaderboard sorting.
"""

from __future__ import annotations

import secrets
import sys
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from models import User, WhaleWallet, WhalePosition  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
async def seed_whales(db_session: AsyncSession) -> list[WhaleWallet]:
    """Seed test database with whale wallets and positions."""
    from datetime import datetime, timezone

    whales = []
    for i in range(5):
        wallet = WhaleWallet(
            address=f"0x{secrets.token_hex(20)}",
            label=f"TestWhale{i + 1}",
            total_volume_usd=float((5 - i) * 500_000),  # Descending volume
            total_pnl_usd=float((5 - i) * 100_000),
            win_rate=0.60 + (i * 0.03),  # 60-72%
            roi_pct=30.0 + (i * 5.0),  # 30-50%
            num_trades=100 + (i * 50),
            num_markets=20 + (i * 10),
            is_active=True,
            last_activity_at=datetime.now(timezone.utc),
            discovered_at=datetime.now(timezone.utc),
        )
        db_session.add(wallet)
        await db_session.flush()

        # Add 2 positions per whale
        for j in range(2):
            pos = WhalePosition(
                wallet_id=wallet.id,
                market_id=f"0x{secrets.token_hex(20)}",
                market_question=f"Test market {i}-{j}?",
                token_id=f"token_{i}_{j}",
                side="YES" if j == 0 else "NO",
                size=float(10_000 + i * 5000),
                avg_price=0.55 + (j * 0.1),
                current_price=0.60 + (j * 0.05),
                pnl_usd=float(500 + i * 200),
                is_open=True,
                opened_at=datetime.now(timezone.utc),
            )
            db_session.add(pos)

        whales.append(wallet)

    await db_session.commit()
    return whales


# ═══════════════════════════════════════════════════════════════════════
# Leaderboard
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_leaderboard(
    client: AsyncClient, auth_headers: dict, seed_whales: list
):
    """Leaderboard returns a list of whale wallets."""
    response = await client.get("/api/whale/leaderboard", headers=auth_headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "whales" in data or isinstance(data, list)
    whales_list = data.get("whales", data) if isinstance(data, dict) else data
    assert len(whales_list) >= 1


@pytest.mark.asyncio
async def test_leaderboard_sorting(
    client: AsyncClient, auth_headers: dict, seed_whales: list
):
    """Leaderboard supports sort_by parameter."""
    for sort_field in ["roi_pct", "win_rate", "total_volume_usd"]:
        response = await client.get(
            f"/api/whale/leaderboard?sort_by={sort_field}",
            headers=auth_headers,
        )
        assert response.status_code == 200, f"Failed for sort_by={sort_field}: {response.text}"


@pytest.mark.asyncio
async def test_leaderboard_pagination(
    client: AsyncClient, auth_headers: dict, seed_whales: list
):
    """Leaderboard supports limit and offset."""
    response = await client.get(
        "/api/whale/leaderboard?limit=2&offset=0",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    whales_list = data.get("whales", data) if isinstance(data, dict) else data
    assert len(whales_list) <= 2


# ═══════════════════════════════════════════════════════════════════════
# Whale Profile
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_whale_profile(
    client: AsyncClient, auth_headers: dict, seed_whales: list
):
    """Can retrieve a specific whale's profile by address."""
    whale = seed_whales[0]
    response = await client.get(
        f"/api/whale/whale/{whale.address}",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["address"] == whale.address
    assert data["label"] == whale.label


@pytest.mark.asyncio
async def test_get_whale_profile_not_found(
    client: AsyncClient, auth_headers: dict
):
    """Non-existent whale address returns 404."""
    response = await client.get(
        f"/api/whale/whale/0x{'00' * 20}",
        headers=auth_headers,
    )
    assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Whale Positions
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_whale_positions(
    client: AsyncClient, auth_headers: dict, seed_whales: list
):
    """Can retrieve positions for a specific whale."""
    whale = seed_whales[0]
    response = await client.get(
        f"/api/whale/whale/{whale.address}/positions",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Verify position structure
    pos = data[0]
    assert "market_question" in pos
    assert "side" in pos
    assert "size" in pos


# ═══════════════════════════════════════════════════════════════════════
# Whale Alerts
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_whale_alerts(
    client: AsyncClient, auth_headers: dict, seed_whales: list
):
    """Whale alerts endpoint returns recent whale activity."""
    response = await client.get("/api/whale/alerts", headers=auth_headers)
    # Accept 200 (has alerts) or 200 with empty list
    assert response.status_code == 200, response.text
    data = response.json()
    # Alerts could be a list or have an "alerts" key
    if isinstance(data, dict):
        assert "alerts" in data
    else:
        assert isinstance(data, list)


# ═══════════════════════════════════════════════════════════════════════
# Whale Discovery
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_whale_discovery(
    client: AsyncClient, auth_headers: dict, seed_whales: list
):
    """Leaderboard shows recently active whales."""
    response = await client.get(
        "/api/whale/leaderboard?active_only=true",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    whales_list = data.get("whales", data) if isinstance(data, dict) else data
    # All returned whales should be active
    for w in whales_list:
        if "is_active" in w:
            assert w["is_active"] is True
