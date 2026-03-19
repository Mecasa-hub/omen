"""Portfolio Tracker — Track positions, PnL, win rate."""
import json
import logging
import aiosqlite
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger("omen.portfolio")

async def get_portfolio_summary(db_path: str, user_id: int) -> dict:
    """Get user portfolio summary."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        # Get all trades
        cursor = await db.execute(
            "SELECT * FROM trade_history WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        )
        trades = [dict(r) for r in await cursor.fetchall()]

        if not trades:
            return {"total_trades": 0, "open_positions": 0, "total_pnl": 0,
                    "win_rate": 0, "best_trade": None, "worst_trade": None,
                    "by_source": {}, "by_side": {}, "daily_pnl": [], "trades": []}

        # Calculate stats
        total = len(trades)
        wins = sum(1 for t in trades if t.get("status") == "won")
        losses = sum(1 for t in trades if t.get("status") == "lost")
        resolved = wins + losses
        win_rate = (wins / resolved * 100) if resolved > 0 else 0

        total_pnl = sum(float(json.loads(t.get("result", "{}")).get("pnl", 0)) 
                       for t in trades if t.get("result"))

        # By source breakdown
        by_source = {}
        for t in trades:
            src = t.get("source", "manual")
            if src not in by_source:
                by_source[src] = {"count": 0, "volume": 0}
            by_source[src]["count"] += 1
            by_source[src]["volume"] += float(t.get("size", 0) or 0)

        # By side
        buys = sum(1 for t in trades if t.get("side") == "BUY")
        sells = total - buys

        # Open positions (placed but not resolved)
        open_pos = [t for t in trades if t.get("status") in ("placed", "filled", "open")]

        # Daily PnL (last 30 days)
        daily = {}
        for t in trades:
            day = t.get("created_at", "")[:10]
            if day not in daily:
                daily[day] = {"trades": 0, "volume": 0}
            daily[day]["trades"] += 1
            daily[day]["volume"] += float(t.get("size", 0) or 0)
        daily_pnl = [{"date": k, **v} for k, v in sorted(daily.items())[-30:]]

        return {
            "total_trades": total,
            "open_positions": len(open_pos),
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "total_volume": round(sum(float(t.get("size", 0) or 0) for t in trades), 2),
            "by_source": by_source,
            "by_side": {"buy": buys, "sell": sells},
            "daily_activity": daily_pnl,
            "open_trades": open_pos[:10],
            "recent_trades": trades[:20],
        }

async def get_performance_chart(db_path: str, user_id: int, days: int = 30) -> list:
    """Get daily performance data for charting."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cursor = await db.execute(
            "SELECT DATE(created_at) as day, COUNT(*) as trades, SUM(size) as volume "
            "FROM trade_history WHERE user_id = ? AND created_at > ? "
            "GROUP BY DATE(created_at) ORDER BY day",
            (user_id, cutoff)
        )
        return [dict(r) for r in await cursor.fetchall()]
