"""Whale Discovery — Auto-detect profitable Polymarket wallets."""
import asyncio
import json
import logging
import httpx
import aiosqlite
from datetime import datetime, timezone

logger = logging.getLogger("omen.whale_discovery")

POLYMARKET_DATA_API = "https://data-api.polymarket.com"

async def discover_whales(min_volume: float = 10000, min_win_rate: float = 60,
                          limit: int = 20) -> list:
    """Discover profitable Polymarket wallets from public data."""
    discovered = []

    async with httpx.AsyncClient(timeout=20) as client:
        # Get recent large trades
        try:
            resp = await client.get(f"{POLYMARKET_DATA_API}/trades",
                                   params={"limit": 200, "min_size": 100})
            if resp.status_code == 200:
                trades = resp.json()
                # Aggregate by wallet
                wallets = {}
                for t in (trades if isinstance(trades, list) else []):
                    addr = t.get("user", t.get("maker", ""))
                    if not addr:
                        continue
                    if addr not in wallets:
                        wallets[addr] = {"address": addr, "trades": 0, "volume": 0,
                                        "buys": 0, "sells": 0}
                    wallets[addr]["trades"] += 1
                    wallets[addr]["volume"] += float(t.get("size", 0) or 0)
                    if t.get("side", "").upper() == "BUY":
                        wallets[addr]["buys"] += 1
                    else:
                        wallets[addr]["sells"] += 1

                # Filter by minimum volume
                for addr, data in wallets.items():
                    if data["volume"] >= min_volume and data["trades"] >= 5:
                        data["avg_size"] = round(data["volume"] / data["trades"], 2)
                        discovered.append(data)
        except Exception as e:
            logger.error(f"Trade discovery failed: {e}")

        # Get leaderboard if available
        try:
            resp2 = await client.get(f"{POLYMARKET_DATA_API}/leaderboard",
                                    params={"limit": 50, "window": "all"})
            if resp2.status_code == 200:
                leaders = resp2.json()
                for l in (leaders if isinstance(leaders, list) else []):
                    addr = l.get("address", l.get("user", ""))
                    if not addr:
                        continue
                    # Check if already discovered
                    existing = [d for d in discovered if d["address"] == addr]
                    if existing:
                        existing[0].update({
                            "pnl": float(l.get("pnl", 0) or 0),
                            "win_rate": float(l.get("win_rate", 0) or 0),
                            "rank": l.get("rank", 0),
                        })
                    else:
                        discovered.append({
                            "address": addr,
                            "pnl": float(l.get("pnl", 0) or 0),
                            "win_rate": float(l.get("win_rate", 0) or 0),
                            "volume": float(l.get("volume", 0) or 0),
                            "trades": int(l.get("num_trades", 0) or 0),
                            "rank": l.get("rank", 0),
                        })
        except Exception as e:
            logger.error(f"Leaderboard discovery failed: {e}")

    # Sort by volume
    discovered.sort(key=lambda x: x.get("volume", 0), reverse=True)
    return discovered[:limit]

async def analyze_wallet(address: str) -> dict:
    """Deep-analyze a specific wallet."""
    async with httpx.AsyncClient(timeout=20) as client:
        result = {"address": address, "trades": [], "markets": set(), 
                 "total_volume": 0, "total_trades": 0}

        try:
            resp = await client.get(f"{POLYMARKET_DATA_API}/trades",
                                   params={"user": address, "limit": 100})
            if resp.status_code == 200:
                trades = resp.json()
                if isinstance(trades, list):
                    result["total_trades"] = len(trades)
                    result["total_volume"] = sum(float(t.get("size", 0) or 0) for t in trades)

                    # Market diversification
                    markets = set()
                    for t in trades:
                        mid = t.get("market", t.get("asset_id", ""))
                        if mid:
                            markets.add(mid)
                    result["unique_markets"] = len(markets)

                    # Trade frequency
                    if len(trades) >= 2:
                        first = trades[-1].get("timestamp", "")
                        last = trades[0].get("timestamp", "")
                        result["first_trade"] = first
                        result["last_trade"] = last

                    # Size distribution
                    sizes = [float(t.get("size", 0) or 0) for t in trades]
                    if sizes:
                        result["avg_size"] = round(sum(sizes) / len(sizes), 2)
                        result["max_size"] = round(max(sizes), 2)
                        result["min_size"] = round(min(sizes), 2)

                    result["recent_trades"] = trades[:10]
        except Exception as e:
            logger.error(f"Wallet analysis failed: {e}")
            result["error"] = str(e)

        result["markets"] = list(result.get("markets", set()))  # Convert set for JSON
        return result

async def save_discovered_whales(db_path: str, whales: list) -> int:
    """Save discovered whales to database."""
    saved = 0
    async with aiosqlite.connect(db_path) as db:
        for w in whales:
            try:
                await db.execute(
                    "INSERT OR IGNORE INTO discovered_whales "
                    "(address, volume, trades, win_rate, pnl, discovered_at) "
                    "VALUES (?, ?, ?, ?, ?, datetime('now'))",
                    (w["address"], w.get("volume", 0), w.get("trades", 0),
                     w.get("win_rate", 0), w.get("pnl", 0))
                )
                saved += 1
            except Exception as e:
                logger.error(f"Save whale failed: {e}")
        await db.commit()
    return saved
