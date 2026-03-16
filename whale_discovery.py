#!/usr/bin/env python3
"""OMEN Whale Discovery Engine.

Scans Polymarket for the most profitable wallets and adds them to the OMEN database.
Runs as a background service, discovering new whales every hour.

Usage:
    python whale_discovery.py              # Run once
    python whale_discovery.py --daemon     # Run continuously
"""

import asyncio
import json
import logging
import sys
import time
import aiosqlite
import httpx
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "omen.db"
LOG_FILE = "/tmp/whale_discovery.log"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE),
    ]
)
logger = logging.getLogger("whale_discovery")

# Polymarket API endpoints
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
PROFILE_API = "https://polymarket.com/api/profile"
ACTIVITY_API = f"{GAMMA_API}/activity"

# Discovery criteria
MIN_TRADES = 50
MIN_VOLUME = 5000  # $5K minimum volume
MIN_WIN_RATE = 52  # Minimum 52% win rate
MAX_WHALES = 100  # Maximum whales to track


class WhaleDiscoveryEngine:
    """Scans Polymarket for profitable wallets."""

    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.discovered = []
        self.scan_count = 0

    async def start(self):
        """Initialize HTTP client."""
        self.client = httpx.AsyncClient(
            timeout=30,
            headers={"User-Agent": "OMEN-WhaleDiscovery/1.0"},
            follow_redirects=True,
        )
        logger.info("🔍 Whale Discovery Engine started")

    async def stop(self):
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()

    async def fetch_recent_activity(self, offset: int = 0, limit: int = 100) -> list:
        """Fetch recent Polymarket trading activity."""
        try:
            resp = await self.client.get(
                ACTIVITY_API,
                params={"offset": offset, "limit": limit, "sortBy": "createdAt", "sortOrder": "desc"}
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"Activity fetch error: {e}")
        return []

    async def fetch_user_positions(self, address: str) -> list:
        """Fetch a user's positions from the CLOB API."""
        try:
            # Try gamma API for user activity
            resp = await self.client.get(
                ACTIVITY_API,
                params={"address": address, "limit": 200}
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.debug(f"Position fetch error for {address}: {e}")
        return []

    async def analyze_wallet(self, address: str) -> Optional[dict]:
        """Analyze a wallet's trading performance."""
        activities = await self.fetch_user_positions(address)
        if not activities or len(activities) < MIN_TRADES:
            return None

        total_trades = 0
        wins = 0
        total_volume = 0.0
        total_pnl = 0.0
        specialties = {}
        last_active = None

        for act in activities:
            if act.get("type") not in ("trade", "buy", "sell"):
                continue

            total_trades += 1
            amount = float(act.get("usdcSize", 0) or act.get("amount", 0) or 0)
            total_volume += amount

            # Track specialty (market category)
            title = act.get("title", "")
            if any(sport in title.lower() for sport in ["win", "score", "goal", "nba", "nfl", "mlb", "soccer", "match"]):
                specialties["Sports"] = specialties.get("Sports", 0) + 1
            elif any(pol in title.lower() for pol in ["election", "president", "vote", "poll", "trump", "biden"]):
                specialties["Politics"] = specialties.get("Politics", 0) + 1
            elif any(crypto in title.lower() for crypto in ["bitcoin", "btc", "eth", "crypto", "price"]):
                specialties["Crypto"] = specialties.get("Crypto", 0) + 1
            else:
                specialties["Mixed"] = specialties.get("Mixed", 0) + 1

            # Track wins (simplified: if outcome matches side and resolved)
            if act.get("outcome") and act.get("side"):
                if str(act.get("outcome")) == str(act.get("side")):
                    wins += 1
                    total_pnl += amount * 0.3  # Approximate 30% return on wins
                else:
                    total_pnl -= amount * 0.5  # Approximate 50% loss

            if not last_active:
                last_active = act.get("createdAt", act.get("timestamp"))

        if total_trades < MIN_TRADES or total_volume < MIN_VOLUME:
            return None

        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        if win_rate < MIN_WIN_RATE:
            return None

        # Determine primary specialty
        specialty = max(specialties, key=specialties.get) if specialties else "Mixed"

        # Generate a display name
        short_addr = f"0x{address[2:6]}...{address[-4:]}"

        return {
            "address": address.lower(),
            "name": f"@{short_addr}",
            "win_rate": round(win_rate, 1),
            "total_trades": total_trades,
            "profit_30d": round(total_pnl, 2),
            "volume_total": round(total_volume, 2),
            "specialty": specialty,
            "last_active": last_active,
        }

    async def scan_for_whales(self) -> list:
        """Scan recent activity to find profitable wallets."""
        self.scan_count += 1
        logger.info(f"🔍 Scan #{self.scan_count} — Fetching recent activity...")

        # Collect unique addresses from recent activity
        all_addresses = set()
        for offset in range(0, 500, 100):
            activities = await self.fetch_recent_activity(offset=offset, limit=100)
            for act in activities:
                addr = act.get("proxyWalletAddress") or act.get("address") or act.get("user")
                if addr and len(addr) == 42:  # Valid ETH address
                    all_addresses.add(addr.lower())
            await asyncio.sleep(0.5)  # Rate limiting

        logger.info(f"  Found {len(all_addresses)} unique addresses")

        # Check which addresses we already track
        existing = set()
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cursor = await db.execute("SELECT address FROM whales")
            rows = await cursor.fetchall()
            existing = {row[0].lower() for row in rows}

        new_addresses = all_addresses - existing
        logger.info(f"  {len(new_addresses)} new addresses to analyze")

        # Analyze each new address
        discovered = []
        for i, addr in enumerate(list(new_addresses)[:50]):  # Limit to 50 per scan
            if i % 10 == 0:
                logger.info(f"  Analyzing {i+1}/{min(len(new_addresses), 50)}...")

            whale = await self.analyze_wallet(addr)
            if whale:
                discovered.append(whale)
                logger.info(
                    f"  🐋 WHALE FOUND: {whale['name']} | "
                    f"Win: {whale['win_rate']}% | "
                    f"Trades: {whale['total_trades']} | "
                    f"Vol: ${whale['volume_total']:,.0f}"
                )
            await asyncio.sleep(0.3)  # Rate limiting

        return discovered

    async def save_whales(self, whales: list):
        """Save discovered whales to the database."""
        if not whales:
            return

        colors = ["#7C3AED", "#3B82F6", "#10B981", "#EF4444", "#F59E0B", "#8B5CF6", "#F97316", "#EC4899", "#14B8A6", "#6366F1"]

        async with aiosqlite.connect(str(DB_PATH)) as db:
            for i, whale in enumerate(whales):
                try:
                    await db.execute(
                        """INSERT OR IGNORE INTO whales
                        (address, name, avatar_color, win_rate, total_trades, profit_30d, volume_total, specialty, followers, is_featured, last_active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)""",
                        (whale["address"], whale["name"], colors[i % len(colors)],
                         whale["win_rate"], whale["total_trades"], whale["profit_30d"],
                         whale["volume_total"], whale["specialty"], whale.get("last_active"))
                    )
                except Exception as e:
                    logger.error(f"Error saving whale {whale['address']}: {e}")
            await db.commit()

        logger.info(f"💾 Saved {len(whales)} new whales to database")

    async def update_existing_whales(self):
        """Re-analyze existing whales to update their stats."""
        async with aiosqlite.connect(str(DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT address, name FROM whales")
            rows = await cursor.fetchall()

        logger.info(f"📊 Updating {len(rows)} existing whales...")
        for row in rows:
            whale = await self.analyze_wallet(row["address"])
            if whale:
                async with aiosqlite.connect(str(DB_PATH)) as db:
                    await db.execute(
                        """UPDATE whales SET win_rate=?, total_trades=?, profit_30d=?,
                        volume_total=?, last_active=? WHERE address=?""",
                        (whale["win_rate"], whale["total_trades"], whale["profit_30d"],
                         whale["volume_total"], whale.get("last_active"), row["address"])
                    )
                    await db.commit()
            await asyncio.sleep(0.5)

        logger.info("✅ Whale stats updated")

    async def get_stats(self) -> dict:
        """Get discovery engine statistics."""
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM whales")
            total = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COUNT(*) FROM whales WHERE is_featured = 1")
            featured = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT AVG(win_rate) FROM whales")
            avg_wr = (await cursor.fetchone())[0] or 0
        return {"total_whales": total, "featured": featured, "avg_win_rate": round(avg_wr, 1), "scans": self.scan_count}

    async def run_once(self):
        """Run a single discovery scan."""
        await self.start()
        try:
            whales = await self.scan_for_whales()
            await self.save_whales(whales)
            stats = await self.get_stats()
            logger.info(f"📊 Stats: {json.dumps(stats)}")
            return whales
        finally:
            await self.stop()

    async def run_daemon(self, interval_hours: float = 1.0):
        """Run continuously, scanning every interval."""
        await self.start()
        logger.info(f"🔄 Daemon mode — scanning every {interval_hours}h")
        try:
            while True:
                try:
                    whales = await self.scan_for_whales()
                    await self.save_whales(whales)
                    await self.update_existing_whales()
                    stats = await self.get_stats()
                    logger.info(f"📊 Stats: {json.dumps(stats)}")
                except Exception as e:
                    logger.error(f"Scan error: {e}")
                await asyncio.sleep(interval_hours * 3600)
        finally:
            await self.stop()


if __name__ == "__main__":
    engine = WhaleDiscoveryEngine()
    if "--daemon" in sys.argv:
        asyncio.run(engine.run_daemon())
    else:
        asyncio.run(engine.run_once())
