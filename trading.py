"""Polymarket Trading Module — Per-User Credentials."""
import asyncio
import json
import logging
import os
from typing import Optional
from datetime import datetime, timezone
from cryptography.fernet import Fernet
from pathlib import Path

logger = logging.getLogger("omen.trading")

# Encryption key for storing user credentials
_KEY_FILE = Path(__file__).parent / "data" / ".trading_key"
_fernet = None

def _get_fernet():
    global _fernet
    if _fernet:
        return _fernet
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if _KEY_FILE.exists():
        key = _KEY_FILE.read_bytes()
    else:
        key = Fernet.generate_key()
        _KEY_FILE.write_bytes(key)
        os.chmod(str(_KEY_FILE), 0o600)
    _fernet = Fernet(key)
    return _fernet

def encrypt_creds(data: dict) -> str:
    """Encrypt user trading credentials."""
    f = _get_fernet()
    return f.encrypt(json.dumps(data).encode()).decode()

def decrypt_creds(encrypted: str) -> dict:
    """Decrypt user trading credentials."""
    f = _get_fernet()
    return json.loads(f.decrypt(encrypted.encode()).decode())

# ── Polymarket Client Per-User ───────────────────────────────────────────
def create_client_for_user(creds: dict):
    """Create a ClobClient for a specific user's credentials."""
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import ApiCreds

        CLOB_API = "https://clob.polymarket.com"

        api_key = creds.get("api_key", "")
        api_secret = creds.get("api_secret", "")
        api_passphrase = creds.get("api_passphrase", "")

        if not all([api_key, api_secret, api_passphrase]):
            return None, "Missing API credentials (key, secret, or passphrase)"

        # Create client with API-only mode (no private key needed)
        client = ClobClient(
            host=CLOB_API,
            chain_id=137,
        )

        client.set_api_creds(ApiCreds(
            api_key=api_key,
            api_secret=api_secret,
            api_passphrase=api_passphrase,
        ))

        return client, None
    except Exception as e:
        logger.error(f"Failed to create client: {e}")
        return None, str(e)

# ── Market Discovery ─────────────────────────────────────────────────────
async def get_markets(limit: int = 20, active_only: bool = True) -> list:
    """Fetch available Polymarket markets via Gamma API."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Use Gamma API - cleaner data with token IDs
            params = {"limit": limit, "active": active_only, "closed": False, "order": "volume", "ascending": False}
            resp = await client.get("https://gamma-api.polymarket.com/markets", params=params)
            resp.raise_for_status()
            markets = resp.json()
            if not isinstance(markets, list):
                markets = markets.get("data", []) if isinstance(markets, dict) else []
            result = []
            for m in markets:
                clob_ids = m.get("clobTokenIds", "")
                if isinstance(clob_ids, str):
                    try:
                        import json as _json
                        clob_ids = _json.loads(clob_ids) if clob_ids.startswith("[") else [clob_ids] if clob_ids else []
                    except:
                        clob_ids = [clob_ids] if clob_ids else []
                tokens = [{"token_id": tid, "outcome": out} for tid, out in zip(
                    clob_ids,
                    ["Yes", "No"] if len(clob_ids) == 2 else [f"Option {i+1}" for i in range(len(clob_ids))]
                )]
                result.append({
                    "condition_id": m.get("conditionId", m.get("condition_id", "")),
                    "question": m.get("question", ""),
                    "tokens": tokens,
                    "volume": float(m.get("volume", 0) or 0),
                    "liquidity": float(m.get("liquidity", 0) or 0),
                    "active": m.get("active", False),
                    "closed": m.get("closed", False),
                    "end_date": m.get("endDate", m.get("end_date_iso", "")),
                    "slug": m.get("slug", ""),
                })
            return result
    except Exception as e:
        logger.error(f"Market fetch failed: {e}")
        return []

async def get_market_price(token_id: str) -> Optional[dict]:
    """Get current price for a market token."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://clob.polymarket.com/price", params={"token_id": token_id, "side": "buy"})
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"Price fetch failed: {e}")
        return None

async def get_market_orderbook(token_id: str) -> Optional[dict]:
    """Get orderbook for a market."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://clob.polymarket.com/book", params={"token_id": token_id})
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"Orderbook fetch failed: {e}")
        return None

# ── Trading Operations ───────────────────────────────────────────────────
def place_market_order(client, token_id: str, side: str, amount: float) -> dict:
    """Place a market order via CLOB client."""
    try:
        from py_clob_client.order_builder.constants import BUY, SELL

        order_side = BUY if side.upper() == "BUY" else SELL

        # Build and sign order
        order = client.create_and_post_order({
            "tokenID": token_id,
            "price": 0.50,  # Will be market order
            "size": amount,
            "side": order_side,
        })

        return {
            "success": True,
            "order_id": order.get("orderID", ""),
            "status": order.get("status", "placed"),
            "token_id": token_id,
            "side": side,
            "amount": amount,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Order placement failed: {e}")
        return {"success": False, "error": str(e)}

def place_limit_order(client, token_id: str, side: str, price: float, size: float) -> dict:
    """Place a limit order via CLOB client."""
    try:
        from py_clob_client.order_builder.constants import BUY, SELL

        order_side = BUY if side.upper() == "BUY" else SELL

        order = client.create_and_post_order({
            "tokenID": token_id,
            "price": price,
            "size": size,
            "side": order_side,
        })

        return {
            "success": True,
            "order_id": order.get("orderID", ""),
            "status": order.get("status", "placed"),
            "token_id": token_id,
            "side": side,
            "price": price,
            "size": size,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Limit order failed: {e}")
        return {"success": False, "error": str(e)}

def get_open_orders(client) -> list:
    """Get user open orders."""
    try:
        orders = client.get_orders()
        return [{"order_id": o.get("id",""), "token_id": o.get("asset_id",""), 
                 "side": o.get("side",""), "price": o.get("price",0), 
                 "size": o.get("original_size",0), "filled": o.get("size_matched",0),
                 "status": o.get("status","")} for o in (orders if isinstance(orders, list) else [])]
    except Exception as e:
        logger.error(f"Get orders failed: {e}")
        return []

def cancel_order(client, order_id: str) -> dict:
    """Cancel an open order."""
    try:
        result = client.cancel(order_id)
        return {"success": True, "order_id": order_id, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

def cancel_all_orders(client) -> dict:
    """Cancel all open orders."""
    try:
        result = client.cancel_all()
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── Copy Trading Logic ───────────────────────────────────────────────────
async def copy_trade(client, whale_address: str, max_amount: float = 10.0) -> dict:
    """Copy the latest trade from a whale address."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(f"https://data-api.polymarket.com/trades", 
                                  params={"user": whale_address, "limit": 1})
            trades = resp.json()
            if not trades:
                return {"success": False, "error": "No recent trades found for whale"}

            latest = trades[0]
            token_id = latest.get("asset_id", "")
            side = latest.get("side", "BUY")
            size = min(float(latest.get("size", 0)), max_amount)
            price = float(latest.get("price", 0.5))

            if not token_id or size <= 0:
                return {"success": False, "error": "Invalid trade data"}

            result = place_limit_order(client, token_id, side, price, size)
            result["copied_from"] = whale_address
            result["original_trade"] = latest
            return result
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── Oracle Auto-Trade ────────────────────────────────────────────────────
async def oracle_trade(client, question: str, verdict: str, confidence: float, 
                       amount: float = 5.0, min_confidence: float = 65.0) -> dict:
    """Place a trade based on Oracle prediction."""
    if confidence < min_confidence:
        return {"success": False, "error": f"Confidence {confidence}% below threshold {min_confidence}%"}

    # Search for matching market
    markets = await get_markets(limit=50)
    best_match = None
    for m in markets:
        q = m.get("question", "").lower()
        if any(word in q for word in question.lower().split()[:3]):
            best_match = m
            break

    if not best_match:
        return {"success": False, "error": "No matching market found on Polymarket"}

    tokens = best_match.get("tokens", [])
    if len(tokens) < 2:
        return {"success": False, "error": "Market has no tradeable tokens"}

    # YES = tokens[0], NO = tokens[1] (standard Polymarket convention)
    token_idx = 0 if verdict == "YES" else 1
    token_id = tokens[token_idx].get("token_id", "")

    # Scale amount by confidence
    scaled_amount = amount * (confidence / 100.0)
    price = confidence / 100.0

    result = place_limit_order(client, token_id, "BUY", round(price, 2), round(scaled_amount, 2))
    result["oracle_question"] = question
    result["oracle_verdict"] = verdict
    result["oracle_confidence"] = confidence
    result["market"] = best_match["question"]
    return result

# ── Risk Management ──────────────────────────────────────────────────────
DEFAULT_RISK_CONFIG = {
    "max_bet_size": 50.0,       # Max single bet in USDC
    "daily_limit": 200.0,       # Max daily spend
    "stop_loss_pct": 35.0,      # Stop loss percentage
    "min_confidence": 65.0,     # Min oracle confidence to auto-trade
    "copy_trade_max": 20.0,     # Max copy trade size
    "max_open_orders": 10,      # Max concurrent open orders
}



async def check_liquidity(token_id: str) -> tuple:
    """Check if a market has sufficient liquidity to trade.
    Returns (ok, best_ask, best_bid, spread, reason).
    CRITICAL: Never trade on illiquid order books (ask=$0.99, bid=$0.01)."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://clob.polymarket.com/book", params={"token_id": token_id})
            resp.raise_for_status()
            book = resp.json()
            asks = book.get("asks", [])
            bids = book.get("bids", [])
            if not asks or not bids:
                return False, 0, 0, 1.0, "Empty order book - no liquidity"
            best_ask = float(asks[0].get("price", 0.99))
            best_bid = float(bids[0].get("price", 0.01))
            spread = best_ask - best_bid
            # CRITICAL: Never trade on extreme spreads
            if best_ask >= 0.90 and best_bid <= 0.10:
                return False, best_ask, best_bid, spread, f"Extreme spread: ask=${best_ask}, bid=${best_bid} - SKIP"
            if spread > 0.50:
                return False, best_ask, best_bid, spread, f"Spread ${spread:.2f} too wide (>$0.50) - SKIP"
            return True, best_ask, best_bid, spread, "OK"
    except Exception as e:
        logger.error(f"Liquidity check failed: {e}")
        return False, 0, 0, 1.0, f"Liquidity check error: {e}"

def validate_trade(amount: float, risk_config: dict = None) -> tuple:
    """Validate trade against risk controls. Returns (ok, reason)."""
    config = risk_config or DEFAULT_RISK_CONFIG
    if amount > config["max_bet_size"]:
        return False, f"Amount ${amount} exceeds max bet size ${config["max_bet_size"]}"
    if amount <= 0:
        return False, "Amount must be positive"
    return True, "OK"
