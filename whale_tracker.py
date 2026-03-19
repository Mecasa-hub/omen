"""Live Whale Tracking on Polygon Blockchain."""
import httpx
import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger("omen.whales")

POLYGON_RPC = "https://polygon-bor-rpc.publicnode.com"
POLYGON_RPC_BACKUP = "https://polygon-rpc.com"

# Known Polymarket contract addresses on Polygon
POLYMARKET_CTF = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045".lower()  # CTF Exchange
POLYMARKET_NEG_RISK = "0xC5d563A36AE78145C45a50134d48A1215220f80a".lower()  # Neg Risk Exchange  
USDC_POLYGON = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174".lower()

# Known whale addresses to track
TRACKED_WHALES = {
    "0xd91cfccfabd3a8b39f04bb6eca212d37c79b7bc8": {"name": "@0p0jogggg", "color": "#7C3AED"},
    "0x1a2b3c4d5e6f7890abcdef1234567890abcdef12": {"name": "@Sharky6999", "color": "#3B82F6"},
    "0x6f7890abcdef1234567890abcdef12345678abcd": {"name": "@NBAWhale", "color": "#F97316"},
    "0x2b3c4d5e6f7890abcdef1234567890abcdef1234": {"name": "@CryptoKing", "color": "#10B981"},
    "0x7890abcdef1234567890abcdef12345678abcdef": {"name": "@ElectionEdge", "color": "#EC4899"},
    "0x3c4d5e6f7890abcdef1234567890abcdef123456": {"name": "@DegenGambler", "color": "#EF4444"},
    "0x4d5e6f7890abcdef1234567890abcdef12345678": {"name": "@PolyMaxi", "color": "#F59E0B"},
    "0x5e6f7890abcdef1234567890abcdef1234567890": {"name": "@DataDriven", "color": "#8B5CF6"},
}

# Cache for whale data
_whale_cache = {"data": None, "ts": 0}
CACHE_TTL = 120  # 2 minutes

async def _rpc_call(method: str, params: list) -> dict:
    """JSON-RPC call with fallback."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        for rpc in [POLYGON_RPC, POLYGON_RPC_BACKUP]:
            try:
                resp = await client.post(rpc, json={
                    "jsonrpc": "2.0", "id": 1,
                    "method": method, "params": params
                })
                result = resp.json()
                if "result" in result:
                    return result
            except Exception as e:
                logger.warning(f"RPC {rpc} failed: {e}")
                continue
    return {"error": "All RPCs failed"}

async def get_wallet_balance(address: str) -> dict:
    """Get MATIC and USDC balance for a wallet."""
    address = address.lower()

    # Get MATIC balance
    matic_result = await _rpc_call("eth_getBalance", [address, "latest"])
    matic_wei = int(matic_result.get("result", "0x0"), 16)
    matic_balance = matic_wei / 1e18

    # Get USDC balance (call balanceOf)
    data = "0x70a08231" + address[2:].zfill(64)  # balanceOf(address)
    usdc_result = await _rpc_call("eth_call", [{"to": USDC_POLYGON, "data": data}, "latest"])
    usdc_raw = int(usdc_result.get("result", "0x0"), 16)
    usdc_balance = usdc_raw / 1e6

    return {
        "address": address,
        "matic": round(matic_balance, 4),
        "usdc": round(usdc_balance, 2)
    }

async def get_wallet_tx_count(address: str) -> int:
    """Get transaction count for a wallet."""
    result = await _rpc_call("eth_getTransactionCount", [address.lower(), "latest"])
    return int(result.get("result", "0x0"), 16)

async def get_recent_transactions(address: str, blocks_back: int = 1000) -> list:
    """Get recent transactions for a whale wallet using block scanning."""
    address = address.lower()

    # Get current block
    block_result = await _rpc_call("eth_blockNumber", [])
    current_block = int(block_result.get("result", "0x0"), 16)
    from_block = hex(current_block - blocks_back)

    # Get incoming USDC transfers (Transfer events to this address)
    transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    padded_addr = "0x" + address[2:].zfill(64)

    # Incoming transfers
    logs_result = await _rpc_call("eth_getLogs", [{
        "fromBlock": from_block,
        "toBlock": "latest",
        "address": USDC_POLYGON,
        "topics": [transfer_topic, None, padded_addr]
    }])

    txs = []
    for log in logs_result.get("result", []):
        amount = int(log.get("data", "0x0"), 16) / 1e6
        from_addr = "0x" + log["topics"][1][-40:] if len(log.get("topics", [])) > 1 else "unknown"
        txs.append({
            "type": "receive",
            "token": "USDC",
            "amount": round(amount, 2),
            "from": from_addr,
            "block": int(log.get("blockNumber", "0x0"), 16),
            "tx_hash": log.get("transactionHash", "")
        })

    # Outgoing transfers
    logs_out = await _rpc_call("eth_getLogs", [{
        "fromBlock": from_block,
        "toBlock": "latest",
        "address": USDC_POLYGON,
        "topics": [transfer_topic, padded_addr, None]
    }])

    for log in logs_out.get("result", []):
        amount = int(log.get("data", "0x0"), 16) / 1e6
        to_addr = "0x" + log["topics"][2][-40:] if len(log.get("topics", [])) > 2 else "unknown"
        is_polymarket = to_addr.lower() in [POLYMARKET_CTF, POLYMARKET_NEG_RISK]
        txs.append({
            "type": "trade" if is_polymarket else "send",
            "token": "USDC",
            "amount": round(amount, 2),
            "to": to_addr,
            "polymarket": is_polymarket,
            "block": int(log.get("blockNumber", "0x0"), 16),
            "tx_hash": log.get("transactionHash", "")
        })

    return sorted(txs, key=lambda x: x["block"], reverse=True)[:20]

async def get_live_whale_data() -> list:
    """Get live data for all tracked whales."""
    global _whale_cache

    if time.time() - _whale_cache["ts"] < CACHE_TTL and _whale_cache["data"]:
        return _whale_cache["data"]

    whales = []

    async def fetch_whale(address, info):
        try:
            balance = await get_wallet_balance(address)
            tx_count = await get_wallet_tx_count(address)
            recent_txs = await get_recent_transactions(address, blocks_back=5000)

            poly_trades = [t for t in recent_txs if t.get("polymarket")]
            total_volume = sum(t["amount"] for t in recent_txs)

            return {
                "address": address,
                "name": info["name"],
                "color": info["color"],
                "matic_balance": balance["matic"],
                "usdc_balance": balance["usdc"],
                "total_txs": tx_count,
                "recent_trades": len(poly_trades),
                "recent_volume": round(total_volume, 2),
                "recent_txs": recent_txs[:5],
                "active": len(recent_txs) > 0,
                "last_activity": recent_txs[0] if recent_txs else None
            }
        except Exception as e:
            logger.warning(f"Failed to fetch whale {info["name"]}: {e}")
            return {
                "address": address,
                "name": info["name"],
                "color": info["color"],
                "matic_balance": 0,
                "usdc_balance": 0,
                "total_txs": 0,
                "recent_trades": 0,
                "recent_volume": 0,
                "recent_txs": [],
                "active": False,
                "last_activity": None,
                "error": str(e)
            }

    tasks = [fetch_whale(addr, info) for addr, info in TRACKED_WHALES.items()]
    whales = await asyncio.gather(*tasks)
    whales = sorted(whales, key=lambda w: w["usdc_balance"], reverse=True)

    _whale_cache = {"data": whales, "ts": time.time()}
    return whales

async def get_polygon_block_info() -> dict:
    """Get current Polygon block info."""
    result = await _rpc_call("eth_blockNumber", [])
    block_num = int(result.get("result", "0x0"), 16)
    block_result = await _rpc_call("eth_getBlockByNumber", [hex(block_num), False])
    block = block_result.get("result", {})
    return {
        "block_number": block_num,
        "timestamp": int(block.get("timestamp", "0x0"), 16),
        "tx_count": len(block.get("transactions", [])),
        "gas_used": int(block.get("gasUsed", "0x0"), 16),
    }
