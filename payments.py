"""Polygon Crypto Payment Verification Module."""
import httpx
import asyncio
import time
import json
import logging
from typing import Optional

logger = logging.getLogger("omen.payments")

PAYMENT_WALLET = "0x135C480C813451eF443A2F60cfaD49EA7197B855".lower()
POLYGON_RPC = "https://polygon-bor-rpc.publicnode.com"
POLYGON_RPC_BACKUP = "https://polygon-rpc.com"

# USDC on Polygon (PoS)
USDC_CONTRACT = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359".lower()  # Native USDC
USDCE_CONTRACT = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174".lower()  # USDC.e (bridged)

# ERC-20 Transfer event topic
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# Credit packages: amount_usd -> credits
CREDIT_RATES = {
    5: 50,    # $5 = 50 credits
    10: 120,  # $10 = 120 credits  
    20: 300,  # $20 = 300 credits
    50: 1000, # $50 = 1000 credits
}

# MATIC price cache
_matic_price_cache = {"price": 0.5, "ts": 0}

async def _rpc_call(method: str, params: list, rpc_url: str = POLYGON_RPC) -> dict:
    """Make a JSON-RPC call to Polygon."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(rpc_url, json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params
            })
            return resp.json()
        except Exception:
            # Try backup
            resp = await client.post(POLYGON_RPC_BACKUP, json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params
            })
            return resp.json()

async def get_matic_price() -> float:
    """Get current MATIC/USD price from CoinGecko."""
    global _matic_price_cache
    if time.time() - _matic_price_cache["ts"] < 300:  # 5min cache
        return _matic_price_cache["price"]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.coingecko.com/api/v3/simple/price?ids=matic-network&vs_currencies=usd")
            price = resp.json()["matic-network"]["usd"]
            _matic_price_cache = {"price": price, "ts": time.time()}
            return price
    except Exception as e:
        logger.warning(f"CoinGecko price fetch failed: {e}, using cached")
        return _matic_price_cache["price"]

async def verify_matic_payment(tx_hash: str) -> Optional[dict]:
    """Verify a MATIC (native) payment transaction."""
    try:
        result = await _rpc_call("eth_getTransactionByHash", [tx_hash])
        tx = result.get("result")
        if not tx:
            return {"verified": False, "error": "Transaction not found"}

        to_addr = (tx.get("to") or "").lower()
        if to_addr != PAYMENT_WALLET:
            return {"verified": False, "error": "Wrong recipient address"}

        # Check confirmation
        receipt_result = await _rpc_call("eth_getTransactionReceipt", [tx_hash])
        receipt = receipt_result.get("result")
        if not receipt or receipt.get("status") != "0x1":
            return {"verified": False, "error": "Transaction failed or pending"}

        # Calculate value in MATIC
        value_wei = int(tx.get("value", "0x0"), 16)
        value_matic = value_wei / 1e18

        # Get USD value
        matic_price = await get_matic_price()
        value_usd = value_matic * matic_price

        # Calculate credits
        credits = calculate_credits(value_usd)

        return {
            "verified": True,
            "tx_hash": tx_hash,
            "from": tx.get("from", "").lower(),
            "to": to_addr,
            "value_matic": round(value_matic, 6),
            "value_usd": round(value_usd, 2),
            "matic_price": matic_price,
            "credits_awarded": credits,
            "block": int(tx.get("blockNumber", "0x0"), 16),
            "confirmations": "confirmed"
        }
    except Exception as e:
        logger.error(f"MATIC payment verification failed: {e}")
        return {"verified": False, "error": str(e)}

async def verify_usdc_payment(tx_hash: str) -> Optional[dict]:
    """Verify a USDC payment transaction on Polygon."""
    try:
        receipt_result = await _rpc_call("eth_getTransactionReceipt", [tx_hash])
        receipt = receipt_result.get("result")
        if not receipt or receipt.get("status") != "0x1":
            return {"verified": False, "error": "Transaction failed or pending"}

        # Look for Transfer events to our wallet
        for log in receipt.get("logs", []):
            contract = log.get("address", "").lower()
            topics = log.get("topics", [])

            if contract not in [USDC_CONTRACT, USDC_E_CONTRACT]:
                continue
            if len(topics) < 3 or topics[0] != TRANSFER_TOPIC:
                continue

            # topics[2] = to address (padded to 32 bytes)
            to_addr = "0x" + topics[2][-40:]
            if to_addr.lower() != PAYMENT_WALLET:
                continue

            # Decode amount (USDC has 6 decimals)
            raw_amount = int(log.get("data", "0x0"), 16)
            amount_usdc = raw_amount / 1e6
            credits = calculate_credits(amount_usdc)

            from_addr = "0x" + topics[1][-40:]

            return {
                "verified": True,
                "tx_hash": tx_hash,
                "from": from_addr.lower(),
                "to": to_addr.lower(),
                "token": "USDC" if contract == USDC_CONTRACT else "USDC.e",
                "value_usdc": round(amount_usdc, 2),
                "value_usd": round(amount_usdc, 2),
                "credits_awarded": credits,
                "block": int(receipt.get("blockNumber", "0x0"), 16),
                "confirmations": "confirmed"
            }

        return {"verified": False, "error": "No USDC transfer to payment wallet found in this transaction"}
    except Exception as e:
        logger.error(f"USDC payment verification failed: {e}")
        return {"verified": False, "error": str(e)}

async def verify_payment(tx_hash: str) -> dict:
    """Auto-detect and verify MATIC or USDC payment."""
    # Try USDC first (check logs)
    usdc_result = await verify_usdc_payment(tx_hash)
    if usdc_result and usdc_result.get("verified"):
        return usdc_result

    # Try native MATIC
    matic_result = await verify_matic_payment(tx_hash)
    if matic_result and matic_result.get("verified"):
        return matic_result

    return {"verified": False, "error": "Transaction not found or not a valid payment to the OMEN wallet"}

def calculate_credits(usd_amount: float) -> int:
    """Calculate credits based on USD amount with tiered pricing."""
    if usd_amount >= 50:
        return int(usd_amount * 20)    # 20 credits/$1 (best rate)
    elif usd_amount >= 20:
        return int(usd_amount * 15)    # 15 credits/$1
    elif usd_amount >= 10:
        return int(usd_amount * 12)    # 12 credits/$1
    elif usd_amount >= 5:
        return int(usd_amount * 10)    # 10 credits/$1
    else:
        return int(usd_amount * 8)     # 8 credits/$1 (minimum)

def get_payment_info() -> dict:
    """Return payment info for frontend."""
    return {
        "wallet": PAYMENT_WALLET,
        "network": "Polygon (MATIC)",
        "chain_id": 137,
        "accepted_tokens": [
            {"symbol": "MATIC", "name": "Polygon", "type": "native"},
            {"symbol": "USDC", "name": "USD Coin", "contract": USDC_CONTRACT, "type": "ERC-20"},
            {"symbol": "USDC.e", "name": "USD Coin (Bridged)", "contract": USDC_E_CONTRACT, "type": "ERC-20"},
        ],
        "credit_rates": [
            {"tier": "Starter", "min_usd": 5, "rate": "10 credits/$1", "example": "$5 = 50 credits"},
            {"tier": "Popular", "min_usd": 10, "rate": "12 credits/$1", "example": "$10 = 120 credits"},
            {"tier": "Pro", "min_usd": 20, "rate": "15 credits/$1", "example": "$20 = 300 credits"},
            {"tier": "Whale", "min_usd": 50, "rate": "20 credits/$1", "example": "$50 = 1,000 credits"},
        ]
    }

USDC_E_CONTRACT = USDCE_CONTRACT  # alias
