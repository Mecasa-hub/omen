"""Backtesting Engine — Test strategies against historical data."""
import asyncio
import json
import logging
import httpx
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("omen.backtest")

POLYMARKET_DATA_API = "https://data-api.polymarket.com"

async def get_resolved_markets(limit: int = 50) -> list:
    """Fetch resolved (completed) Polymarket markets for backtesting."""
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.get("https://gamma-api.polymarket.com/markets",
                                   params={"limit": limit, "closed": True, "order": "volume", "ascending": False})
            resp.raise_for_status()
            markets = resp.json()
            if not isinstance(markets, list):
                markets = markets.get("data", []) if isinstance(markets, dict) else []
            return [{
                "question": m.get("question", ""),
                "outcome": m.get("outcome", m.get("resolution", "")),
                "volume": float(m.get("volume", 0) or 0),
                "end_date": m.get("endDate", ""),
                "condition_id": m.get("conditionId", ""),
                "slug": m.get("slug", ""),
            } for m in markets if m.get("closed")]
        except Exception as e:
            logger.error(f"Resolved markets fetch failed: {e}")
            return []

async def run_backtest(oracle_fn, markets: list = None, agent_count: int = 5,
                       min_confidence: float = 55) -> dict:
    """Run backtest: Oracle predicts resolved markets, compare to outcomes."""
    if markets is None:
        markets = await get_resolved_markets(limit=30)

    results = {
        "total_markets": len(markets),
        "predictions": 0,
        "correct": 0,
        "incorrect": 0,
        "skipped": 0,
        "accuracy": 0,
        "avg_confidence": 0,
        "by_confidence": {"high": {"correct": 0, "total": 0}, 
                         "medium": {"correct": 0, "total": 0},
                         "low": {"correct": 0, "total": 0}},
        "simulated_pnl": 0,
        "details": [],
    }

    confidences = []

    for market in markets:
        question = market.get("question", "")
        actual_outcome = market.get("outcome", "").upper()

        if not question or not actual_outcome:
            results["skipped"] += 1
            continue

        # Normalize outcome
        if actual_outcome in ("YES", "TRUE", "1"):
            actual = "YES"
        elif actual_outcome in ("NO", "FALSE", "0"):
            actual = "NO"
        else:
            results["skipped"] += 1
            continue

        try:
            oracle_result = await oracle_fn(question)
            verdict = oracle_result.get("verdict", "")
            confidence = oracle_result.get("confidence", 0)

            if confidence < min_confidence:
                results["skipped"] += 1
                continue

            results["predictions"] += 1
            confidences.append(confidence)
            is_correct = verdict == actual

            if is_correct:
                results["correct"] += 1
                pnl = (confidence / 100.0) * 10  # Simulated $10 bet
            else:
                results["incorrect"] += 1
                pnl = -10  # Lost the bet

            results["simulated_pnl"] += pnl

            # Confidence buckets
            if confidence >= 80:
                bucket = "high"
            elif confidence >= 65:
                bucket = "medium"
            else:
                bucket = "low"
            results["by_confidence"][bucket]["total"] += 1
            if is_correct:
                results["by_confidence"][bucket]["correct"] += 1

            results["details"].append({
                "question": question[:80],
                "predicted": verdict,
                "actual": actual,
                "confidence": confidence,
                "correct": is_correct,
                "pnl": round(pnl, 2),
            })

        except Exception as e:
            logger.error(f"Backtest prediction failed for {question[:30]}: {e}")
            results["skipped"] += 1

    # Calculate summary
    if results["predictions"] > 0:
        results["accuracy"] = round(results["correct"] / results["predictions"] * 100, 1)
    if confidences:
        results["avg_confidence"] = round(sum(confidences) / len(confidences), 1)
    results["simulated_pnl"] = round(results["simulated_pnl"], 2)

    # Accuracy by confidence bucket
    for bucket in results["by_confidence"].values():
        if bucket["total"] > 0:
            bucket["accuracy"] = round(bucket["correct"] / bucket["total"] * 100, 1)
        else:
            bucket["accuracy"] = 0

    return results
