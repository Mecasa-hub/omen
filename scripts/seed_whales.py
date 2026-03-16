#!/usr/bin/env python3
"""OMEN — Seed Whale Wallets Script.

Populates the whale_wallets and whale_positions tables with realistic
data based on known top Polymarket traders.

Usage:
    python scripts/seed_whales.py
"""

import asyncio
import logging
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend to Python path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("seed_whales")

# ═══════════════════════════════════════════════════════════════════
# Known Polymarket Whale Data (realistic, based on public leaderboards)
# ═══════════════════════════════════════════════════════════════════
WHALE_DATA = [
    {
        "address": "0xB7c6EC08bC5A7F8E2cc25b14bBA1f6D3b8d9cE10",
        "label": "Theo4",
        "total_volume_usd": 2_450_000.00,
        "total_pnl_usd": 380_000.00,
        "win_rate": 0.72,
        "roi_pct": 45.2,
        "num_trades": 342,
        "num_markets": 87,
    },
    {
        "address": "0xA1D6cF3892b4F7E321Cb8903fA6548eE7102a5Fd",
        "label": "Domer",
        "total_volume_usd": 4_800_000.00,
        "total_pnl_usd": 720_000.00,
        "win_rate": 0.68,
        "roi_pct": 38.7,
        "num_trades": 891,
        "num_markets": 203,
    },
    {
        "address": "0x3Fc2D89a54f63e4b5821E9fB7bAe5c21C85dE3a7",
        "label": "PredictionKing",
        "total_volume_usd": 1_200_000.00,
        "total_pnl_usd": 285_000.00,
        "win_rate": 0.76,
        "roi_pct": 52.1,
        "num_trades": 178,
        "num_markets": 56,
    },
    {
        "address": "0x8eB94c2F2679E2C77A08D44328D86B7351b9fE15",
        "label": "SharkyBets",
        "total_volume_usd": 3_100_000.00,
        "total_pnl_usd": 410_000.00,
        "win_rate": 0.65,
        "roi_pct": 33.4,
        "num_trades": 567,
        "num_markets": 142,
    },
    {
        "address": "0xC42f8901E2D4aDe7F6b3e2c9B71098bF5a6c7d80",
        "label": "PolyWhale",
        "total_volume_usd": 8_900_000.00,
        "total_pnl_usd": 1_250_000.00,
        "win_rate": 0.71,
        "roi_pct": 41.8,
        "num_trades": 1_423,
        "num_markets": 312,
    },
    {
        "address": "0xD5A70bC39dF8123E45A9C7809B6e2F41aE3c8F92",
        "label": "CryptoOracle99",
        "total_volume_usd": 950_000.00,
        "total_pnl_usd": 195_000.00,
        "win_rate": 0.74,
        "roi_pct": 48.9,
        "num_trades": 134,
        "num_markets": 41,
    },
    {
        "address": "0xE7F3c4A8BD5612Da09b1e4Fe38A7c0253D91eA6b",
        "label": "MidnightTrader",
        "total_volume_usd": 1_750_000.00,
        "total_pnl_usd": 310_000.00,
        "win_rate": 0.69,
        "roi_pct": 37.5,
        "num_trades": 289,
        "num_markets": 78,
    },
    {
        "address": "0xF1A25bE89cC73D4561eFd82B03a19D67F4c0aB58",
        "label": "AlphaSeeker",
        "total_volume_usd": 5_200_000.00,
        "total_pnl_usd": 890_000.00,
        "win_rate": 0.73,
        "roi_pct": 44.1,
        "num_trades": 734,
        "num_markets": 189,
    },
    {
        "address": "0x2aB8dE9120f47C83619A5bD3F02E5eC7681d94A3",
        "label": "ElectionGuru",
        "total_volume_usd": 6_300_000.00,
        "total_pnl_usd": 1_050_000.00,
        "win_rate": 0.70,
        "roi_pct": 39.6,
        "num_trades": 1_056,
        "num_markets": 245,
    },
    {
        "address": "0x5cD7F3412eA08bB56C921aD3E87f1A8c0F46d5E9",
        "label": "WhaleWatcher420",
        "total_volume_usd": 780_000.00,
        "total_pnl_usd": 142_000.00,
        "win_rate": 0.67,
        "roi_pct": 35.8,
        "num_trades": 201,
        "num_markets": 63,
    },
    {
        "address": "0x9eF4bA7321CD685E0A3c12F94817B60D2a5E8c71",
        "label": "DegenCapital",
        "total_volume_usd": 2_100_000.00,
        "total_pnl_usd": 275_000.00,
        "win_rate": 0.63,
        "roi_pct": 29.8,
        "num_trades": 445,
        "num_markets": 112,
    },
    {
        "address": "0x6bA1eC83F72D05419E8F3A72B9C6D1c534Ba90D2",
        "label": "InfoEdgeTrader",
        "total_volume_usd": 3_400_000.00,
        "total_pnl_usd": 620_000.00,
        "win_rate": 0.75,
        "roi_pct": 50.3,
        "num_trades": 412,
        "num_markets": 98,
    },
]

# Sample market positions for whales
SAMPLE_MARKETS = [
    {
        "market_id": "0x" + uuid.uuid4().hex[:40],
        "market_question": "Will Bitcoin exceed $100,000 by April 2026?",
        "token_id": "71321045663652420386911009203" + "10",
    },
    {
        "market_id": "0x" + uuid.uuid4().hex[:40],
        "market_question": "Will Ethereum reach $5,000 by Q2 2026?",
        "token_id": "71321045663652420386911009203" + "20",
    },
    {
        "market_id": "0x" + uuid.uuid4().hex[:40],
        "market_question": "Will the Fed cut rates in March 2026?",
        "token_id": "71321045663652420386911009203" + "30",
    },
    {
        "market_id": "0x" + uuid.uuid4().hex[:40],
        "market_question": "Will Trump win the 2028 Republican primary?",
        "token_id": "71321045663652420386911009203" + "40",
    },
    {
        "market_id": "0x" + uuid.uuid4().hex[:40],
        "market_question": "Will SOL flip ETH in market cap by 2027?",
        "token_id": "71321045663652420386911009203" + "50",
    },
    {
        "market_id": "0x" + uuid.uuid4().hex[:40],
        "market_question": "Will the US pass a stablecoin bill in 2026?",
        "token_id": "71321045663652420386911009203" + "60",
    },
    {
        "market_id": "0x" + uuid.uuid4().hex[:40],
        "market_question": "Will AI generate a hit #1 song by end of 2026?",
        "token_id": "71321045663652420386911009203" + "70",
    },
    {
        "market_id": "0x" + uuid.uuid4().hex[:40],
        "market_question": "Will SpaceX Starship complete an orbital flight in Q1 2026?",
        "token_id": "71321045663652420386911009203" + "80",
    },
]


async def seed_whales() -> None:
    """Insert whale wallets and sample positions into the database."""
    import random

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from database import async_session_factory, engine
    from models import WhalePosition, WhaleWallet

    logger.info("=" * 60)
    logger.info("  OMEN — Seed Whale Wallets")
    logger.info("=" * 60)

    now = datetime.now(timezone.utc)
    created_wallets = 0
    skipped_wallets = 0
    created_positions = 0

    async with async_session_factory() as session:  # type: AsyncSession
        for whale_data in WHALE_DATA:
            # Check if wallet already exists
            result = await session.execute(
                select(WhaleWallet).where(
                    WhaleWallet.address == whale_data["address"]
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                logger.info(
                    "  ⏭️  Skipping %s (%s) — already exists",
                    whale_data["label"],
                    whale_data["address"][:10] + "...",
                )
                skipped_wallets += 1
                continue

            # Create whale wallet
            first_seen = now - timedelta(days=random.randint(60, 365))
            last_activity = now - timedelta(hours=random.randint(1, 72))

            wallet = WhaleWallet(
                address=whale_data["address"],
                label=whale_data["label"],
                total_volume_usd=whale_data["total_volume_usd"],
                total_pnl_usd=whale_data["total_pnl_usd"],
                win_rate=whale_data["win_rate"],
                roi_pct=whale_data["roi_pct"],
                num_trades=whale_data["num_trades"],
                num_markets=whale_data["num_markets"],
                is_active=True,
                last_activity_at=last_activity,
                discovered_at=first_seen,
            )
            session.add(wallet)
            await session.flush()  # Get wallet.id
            created_wallets += 1

            logger.info(
                "  ✅ Created whale: %s | Vol: $%s | ROI: %.1f%% | WR: %.0f%%",
                whale_data["label"],
                f"{whale_data['total_volume_usd']:,.0f}",
                whale_data["roi_pct"],
                whale_data["win_rate"] * 100,
            )

            # Create 2-5 sample positions for each whale
            num_positions = random.randint(2, 5)
            selected_markets = random.sample(
                SAMPLE_MARKETS, min(num_positions, len(SAMPLE_MARKETS))
            )

            for market in selected_markets:
                side = random.choice(["YES", "NO"])
                size = round(random.uniform(5_000, 150_000), 2)
                avg_price = round(random.uniform(0.25, 0.80), 4)
                current_price = round(
                    avg_price + random.uniform(-0.15, 0.20), 4
                )
                current_price = max(0.01, min(0.99, current_price))
                pnl = round((current_price - avg_price) * size, 2)
                is_open = random.random() > 0.3  # 70% open

                position = WhalePosition(
                    wallet_id=wallet.id,
                    market_id=market["market_id"],
                    market_question=market["market_question"],
                    token_id=market["token_id"],
                    side=side,
                    size=size,
                    avg_price=avg_price,
                    current_price=current_price,
                    pnl_usd=pnl,
                    is_open=is_open,
                    opened_at=now - timedelta(days=random.randint(1, 30)),
                    closed_at=(
                        now - timedelta(hours=random.randint(1, 48))
                        if not is_open
                        else None
                    ),
                )
                session.add(position)
                created_positions += 1

        await session.commit()

    logger.info("")
    logger.info("Seeding complete:")
    logger.info("  Wallets created:  %d", created_wallets)
    logger.info("  Wallets skipped:  %d", skipped_wallets)
    logger.info("  Positions created: %d", created_positions)
    logger.info("  Total whales:     %d", created_wallets + skipped_wallets)

    await engine.dispose()


def main() -> None:
    """Entry point."""
    try:
        asyncio.run(seed_whales())
    except KeyboardInterrupt:
        logger.info("Seeding interrupted.")
        sys.exit(1)
    except Exception as exc:
        logger.error("Seeding failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
