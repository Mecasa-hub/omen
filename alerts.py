"""Alert System — Whale moves, Oracle streaks, market events."""
import asyncio
import json
import logging
import aiosqlite
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("omen.alerts")

# Alert types
ALERT_TYPES = {
    "whale_move": {"icon": "whale", "priority": "high"},
    "oracle_streak": {"icon": "fire", "priority": "medium"},
    "price_change": {"icon": "chart", "priority": "medium"},
    "trade_filled": {"icon": "check", "priority": "low"},
    "trade_won": {"icon": "trophy", "priority": "high"},
    "trade_lost": {"icon": "x", "priority": "medium"},
    "market_event": {"icon": "bell", "priority": "medium"},
    "risk_warning": {"icon": "shield", "priority": "high"},
    "autopilot": {"icon": "robot", "priority": "medium"},
}

async def create_alert(db_path: str, user_id: int, alert_type: str, 
                       title: str, message: str, data: dict = None) -> int:
    """Create a new alert for a user."""
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "INSERT INTO alerts (user_id, type, title, message, data, created_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (user_id, alert_type, title, message, json.dumps(data or {}))
        )
        await db.commit()
        return cursor.lastrowid

async def get_alerts(db_path: str, user_id: int, unread_only: bool = False, 
                     limit: int = 50) -> list:
    """Get alerts for a user."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM alerts WHERE user_id = ?"
        params = [user_id]
        if unread_only:
            query += " AND read = 0"
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cursor = await db.execute(query, params)
        return [dict(r) for r in await cursor.fetchall()]

async def mark_read(db_path: str, user_id: int, alert_id: int = None) -> None:
    """Mark alert(s) as read."""
    async with aiosqlite.connect(db_path) as db:
        if alert_id:
            await db.execute("UPDATE alerts SET read = 1 WHERE id = ? AND user_id = ?",
                           (alert_id, user_id))
        else:
            await db.execute("UPDATE alerts SET read = 1 WHERE user_id = ?", (user_id,))
        await db.commit()

async def get_unread_count(db_path: str, user_id: int) -> int:
    """Get count of unread alerts."""
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM alerts WHERE user_id = ? AND read = 0", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

async def delete_old_alerts(db_path: str, days: int = 30) -> int:
    """Delete alerts older than N days."""
    async with aiosqlite.connect(db_path) as db:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cursor = await db.execute("DELETE FROM alerts WHERE created_at < ?", (cutoff,))
        await db.commit()
        return cursor.rowcount
