"""Auto-Pilot — Fully automated trading based on Oracle + Whales."""
import asyncio
import json
import logging
import aiosqlite
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("omen.autopilot")

# Risk profiles
RISK_PROFILES = {
    "conservative": {
        "name": "Conservative",
        "icon": "shield",
        "min_confidence": 80,
        "max_bet_size": 10.0,
        "daily_limit": 50.0,
        "max_concurrent": 3,
        "require_whale_agreement": True,
        "min_whale_agree_pct": 60,
        "scan_interval_min": 30,
        "stop_loss_pct": 20,
    },
    "balanced": {
        "name": "Balanced",
        "icon": "scale",
        "min_confidence": 65,
        "max_bet_size": 25.0,
        "daily_limit": 150.0,
        "max_concurrent": 5,
        "require_whale_agreement": False,
        "min_whale_agree_pct": 40,
        "scan_interval_min": 15,
        "stop_loss_pct": 30,
    },
    "aggressive": {
        "name": "Aggressive",
        "icon": "flame",
        "min_confidence": 55,
        "max_bet_size": 50.0,
        "daily_limit": 300.0,
        "max_concurrent": 10,
        "require_whale_agreement": False,
        "min_whale_agree_pct": 0,
        "scan_interval_min": 5,
        "stop_loss_pct": 40,
    },
}

async def get_autopilot_status(db_path: str, user_id: int) -> dict:
    """Get auto-pilot configuration and status."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM autopilot_config WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return {"enabled": False, "risk_profile": "balanced", 
                    "config": RISK_PROFILES["balanced"],
                    "stats": {"trades_today": 0, "spent_today": 0, "pnl_today": 0}}

        config = dict(row)
        profile = config.get("risk_profile", "balanced")

        # Get today stats
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cursor2 = await db.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(size),0) as vol FROM trade_history "
            "WHERE user_id = ? AND source = 'autopilot' AND created_at LIKE ?",
            (user_id, f"{today}%")
        )
        stats_row = await cursor2.fetchone()

        return {
            "enabled": bool(config.get("enabled", 0)),
            "risk_profile": profile,
            "config": RISK_PROFILES.get(profile, RISK_PROFILES["balanced"]),
            "custom_config": json.loads(config.get("custom_config", "{}")) if config.get("custom_config") else {},
            "markets_filter": config.get("markets_filter", "all"),
            "stats": {
                "trades_today": stats_row[0] if stats_row else 0,
                "spent_today": round(float(stats_row[1]) if stats_row else 0, 2),
            },
            "last_scan": config.get("last_scan", ""),
            "last_trade": config.get("last_trade", ""),
        }

async def update_autopilot(db_path: str, user_id: int, enabled: bool = None,
                           risk_profile: str = None, markets_filter: str = None) -> dict:
    """Update auto-pilot settings."""
    async with aiosqlite.connect(db_path) as db:
        # Upsert
        existing = await db.execute("SELECT user_id FROM autopilot_config WHERE user_id = ?", (user_id,))
        row = await existing.fetchone()

        if not row:
            await db.execute(
                "INSERT INTO autopilot_config (user_id, enabled, risk_profile, markets_filter) VALUES (?,?,?,?)",
                (user_id, 1 if enabled else 0, risk_profile or "balanced", markets_filter or "all")
            )
        else:
            updates = []
            params = []
            if enabled is not None:
                updates.append("enabled = ?")
                params.append(1 if enabled else 0)
            if risk_profile:
                updates.append("risk_profile = ?")
                params.append(risk_profile)
            if markets_filter:
                updates.append("markets_filter = ?")
                params.append(markets_filter)
            if updates:
                params.append(user_id)
                await db.execute(f"UPDATE autopilot_config SET {', '.join(updates)} WHERE user_id = ?", params)
        await db.commit()
    return await get_autopilot_status(db_path, user_id)

async def scan_opportunities(db_path: str, user_id: int, oracle_fn, markets_fn, 
                              whale_data: list = None) -> list:
    """Scan markets for auto-pilot trading opportunities."""
    status = await get_autopilot_status(db_path, user_id)
    if not status["enabled"]:
        return []

    config = status["config"]
    opportunities = []

    # Get active markets
    markets = await markets_fn(limit=30)

    for market in markets:
        question = market.get("question", "")
        if not question:
            continue

        tokens = market.get("tokens", [])
        if not tokens:
            continue

        # Run Oracle on market
        try:
            oracle_result = await oracle_fn(question)
            confidence = oracle_result.get("confidence", 0)
            verdict = oracle_result.get("verdict", "")

            if confidence < config["min_confidence"]:
                continue

            # Check whale agreement if required
            whale_agree_pct = 0
            if whale_data and config.get("require_whale_agreement"):
                # Simplified whale check
                whale_agree_pct = oracle_result.get("whale_agreement", 0)
                if whale_agree_pct < config.get("min_whale_agree_pct", 0):
                    continue

            # Calculate position size (Kelly-inspired)
            edge = (confidence - 50) / 100.0  # Edge over 50/50
            base_size = min(config["max_bet_size"], config["daily_limit"] * edge)
            size = max(1.0, round(base_size, 2))

            # Token selection
            token_idx = 0 if verdict == "YES" else (1 if len(tokens) > 1 else 0)
            token_id = tokens[token_idx].get("token_id", "")

            opportunities.append({
                "market": question,
                "verdict": verdict,
                "confidence": confidence,
                "token_id": token_id,
                "side": "BUY",
                "size": size,
                "price": confidence / 100.0,
                "whale_agreement": whale_agree_pct,
                "edge": round(edge * 100, 1),
            })
        except Exception as e:
            logger.error(f"Oracle scan failed for {question[:30]}: {e}")
            continue

    # Sort by edge (best opportunities first)
    opportunities.sort(key=lambda x: x["edge"], reverse=True)

    # Limit by max concurrent
    return opportunities[:config.get("max_concurrent", 5)]

async def execute_autopilot_trades(db_path: str, user_id: int, opportunities: list,
                                    trade_fn) -> list:
    """Execute auto-pilot trades."""
    results = []
    status = await get_autopilot_status(db_path, user_id)
    config = status["config"]
    remaining_budget = config["daily_limit"] - status["stats"]["spent_today"]

    for opp in opportunities:
        if remaining_budget <= 0:
            break

        size = min(opp["size"], remaining_budget)
        if size < 1.0:
            break

        try:
            result = await trade_fn(
                token_id=opp["token_id"],
                side=opp["side"],
                price=opp["price"],
                size=size
            )
            result["market"] = opp["market"]
            result["confidence"] = opp["confidence"]
            result["source"] = "autopilot"
            results.append(result)
            remaining_budget -= size

            # Log trade
            async with aiosqlite.connect(db_path) as db:
                await db.execute(
                    "INSERT INTO trade_history (user_id, order_id, token_id, market_question, "
                    "side, price, size, status, source) VALUES (?,?,?,?,?,?,?,?,?)",
                    (user_id, result.get("order_id", ""), opp["token_id"], opp["market"],
                     opp["side"], opp["price"], size, "placed", "autopilot")
                )
                await db.execute(
                    "UPDATE autopilot_config SET last_trade = datetime('now') WHERE user_id = ?",
                    (user_id,)
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Autopilot trade failed: {e}")
            results.append({"success": False, "error": str(e), "market": opp["market"]})

    return results
