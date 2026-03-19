"""Backtesting Engine — Test strategies against historical data."""
import asyncio
import json
import logging
import httpx
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("omen.backtest")

GAMMA_API = "https://gamma-api.polymarket.com"


def _extract_outcome(market: dict) -> str:
    """Extract the winning outcome from a resolved Polymarket market.
    
    The Gamma API returns:
    - outcomes: ["Yes", "No"] or ["TeamA", "TeamB"] etc.
    - outcomePrices: ["1", "0"] or ["0", "1"] -- winner has price "1"
    """
    outcomes = market.get("outcomes", "")
    prices = market.get("outcomePrices", "")
    
    # Parse JSON strings if needed
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except (json.JSONDecodeError, TypeError):
            return ""
    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except (json.JSONDecodeError, TypeError):
            return ""
    
    if not outcomes or not prices or len(outcomes) != len(prices):
        return ""
    
    # Find the winning outcome (price == "1" or closest to 1)
    for i, price in enumerate(prices):
        try:
            if float(price) >= 0.99:  # Winner
                return outcomes[i].strip()
        except (ValueError, TypeError):
            continue
    
    return ""


def _normalize_outcome(outcome: str) -> str:
    """Normalize outcome to YES/NO for binary markets."""
    upper = outcome.upper().strip()
    if upper in ("YES", "TRUE", "1"):
        return "YES"
    elif upper in ("NO", "FALSE", "0"):
        return "NO"
    return upper  # Return as-is for non-binary (team names etc.)


async def get_resolved_markets(limit: int = 50) -> list:
    """Fetch resolved (completed) Polymarket markets for backtesting.
    Focuses on Yes/No binary markets for Oracle compatibility."""
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.get(f"{GAMMA_API}/markets",
                                   params={"limit": min(limit * 3, 200),
                                           "closed": True,
                                           "order": "volume",
                                           "ascending": False})
            resp.raise_for_status()
            markets = resp.json()
            if not isinstance(markets, list):
                markets = markets.get("data", []) if isinstance(markets, dict) else []
            
            results = []
            for m in markets:
                if not m.get("closed"):
                    continue
                    
                winner = _extract_outcome(m)
                if not winner:
                    continue
                
                # Parse outcomes list
                outcomes_raw = m.get("outcomes", "[]")
                if isinstance(outcomes_raw, str):
                    try:
                        outcomes_list = json.loads(outcomes_raw)
                    except Exception:
                        outcomes_list = []
                else:
                    outcomes_list = outcomes_raw or []
                
                # Determine if binary Yes/No market
                outcomes_upper = [o.upper().strip() for o in outcomes_list]
                is_binary = set(outcomes_upper) <= {"YES", "NO"}
                
                results.append({
                    "question": m.get("question", ""),
                    "outcome": winner,
                    "outcome_normalized": _normalize_outcome(winner),
                    "is_binary": is_binary,
                    "volume": float(m.get("volume", 0) or 0),
                    "end_date": m.get("endDate", ""),
                    "condition_id": m.get("conditionId", ""),
                    "slug": m.get("slug", ""),
                })
                
                if len(results) >= limit:
                    break
            
            return results
        except Exception as e:
            logger.error(f"Resolved markets fetch failed: {e}")
            return []


async def run_backtest(oracle_fn, markets: list = None, agent_count: int = 5,
                       min_confidence: float = 55) -> dict:
    """Run backtest: Oracle predicts resolved markets, compare to outcomes.
    
    For binary (Yes/No) markets: Compare Oracle YES/NO vs actual.
    For non-binary markets: Oracle predicts the question, we compare verdict.
    """
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
        actual_outcome = market.get("outcome_normalized", "")
        is_binary = market.get("is_binary", False)

        if not question or not actual_outcome:
            results["skipped"] += 1
            continue

        if is_binary:
            actual = actual_outcome
        else:
            actual = actual_outcome

        try:
            oracle_result = await oracle_fn(question)
            verdict = oracle_result.get("verdict", "")
            confidence = oracle_result.get("confidence", 0)

            if confidence < min_confidence:
                results["skipped"] += 1
                continue

            results["predictions"] += 1
            confidences.append(confidence)
            
            # Determine correctness
            is_correct = verdict.upper() == actual.upper()

            if is_correct:
                results["correct"] += 1
                pnl = (confidence / 100.0) * 10
            else:
                results["incorrect"] += 1
                pnl = -10

            results["simulated_pnl"] += pnl

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

    for bucket in results["by_confidence"].values():
        if bucket["total"] > 0:
            bucket["accuracy"] = round(bucket["correct"] / bucket["total"] * 100, 1)
        else:
            bucket["accuracy"] = 0

    return results
