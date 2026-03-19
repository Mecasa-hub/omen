import os
from dotenv import load_dotenv
load_dotenv()
"""NOWPayments Gateway Integration for OMEN.

OpenRouter-style credits page with hosted crypto checkout.
Funds go directly to merchant wallet via NOWPayments.
"""
import httpx
import hmac
import hashlib
import json
import time
import logging
from typing import Optional, Dict

logger = logging.getLogger("omen.payments")

# NOWPayments configuration
NOWPAYMENTS_API_KEY = os.environ.get("NOWPAYMENTS_API_KEY", "")
NOWPAYMENTS_IPN_SECRET = "GSScDvP5M3Y8ttPn/5uSiyBf6H3/Sqj6"
NOWPAYMENTS_API = "https://api.nowpayments.io/v1"

PAYMENT_WALLET = "0x135C480C813451eF443A2F60cfaD49EA7197B855"

# Credit conversion: $1 USD = X credits (tiered)
CREDIT_TIERS = [
    (50, 20, "Whale"),     # $50+ = 20 credits/$1
    (20, 15, "Pro"),       # $20+ = 15 credits/$1
    (10, 12, "Popular"),   # $10+ = 12 credits/$1
    (5, 10, "Starter"),    # $5+  = 10 credits/$1
    (0, 8, "Micro"),       # <$5  = 8 credits/$1
]

# Supported crypto currencies on NOWPayments
SUPPORTED_CURRENCIES = [
    {"code": "matic", "name": "Polygon MATIC", "network": "Polygon"},
    {"code": "usdcmatic", "name": "USDC (Polygon)", "network": "Polygon"},
    {"code": "usdtmatic", "name": "USDT (Polygon)", "network": "Polygon"},
    {"code": "btc", "name": "Bitcoin", "network": "Bitcoin"},
    {"code": "eth", "name": "Ethereum", "network": "Ethereum"},
    {"code": "usdc", "name": "USDC (ERC-20)", "network": "Ethereum"},
    {"code": "usdt", "name": "USDT (ERC-20)", "network": "Ethereum"},
    {"code": "usdterc20", "name": "USDT (ERC-20)", "network": "Ethereum"},
    {"code": "usdttrc20", "name": "USDT (TRC-20)", "network": "Tron"},
    {"code": "sol", "name": "Solana", "network": "Solana"},
    {"code": "usdcsol", "name": "USDC (Solana)", "network": "Solana"},
]


def _headers():
    return {"x-api-key": NOWPAYMENTS_API_KEY, "Content-Type": "application/json"}


def calculate_credits(usd_amount: float) -> tuple:
    """Calculate credits from USD amount. Returns (credits, tier_name, rate)."""
    for min_usd, rate, name in CREDIT_TIERS:
        if usd_amount >= min_usd:
            return (int(usd_amount * rate), name, rate)
    return (0, "None", 0)


async def get_api_status() -> dict:
    """Check NOWPayments API status."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{NOWPAYMENTS_API}/status", headers=_headers())
            return resp.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def get_estimate(amount_usd: float, pay_currency: str = "matic") -> dict:
    """Get estimated crypto amount for a USD payment."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{NOWPAYMENTS_API}/estimate",
                params={"amount": amount_usd, "currency_from": "usd", "currency_to": pay_currency},
                headers=_headers()
            )
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


async def get_min_amount(pay_currency: str = "matic") -> dict:
    """Get minimum payment amount for a currency."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{NOWPAYMENTS_API}/min-amount",
                params={"currency_from": pay_currency, "currency_to": "usd"},
                headers=_headers()
            )
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


async def create_invoice(amount_usd: float, order_id: str, order_description: str = "OMEN Credits") -> dict:
    """Create a NOWPayments invoice (hosted checkout page).

    This creates a hosted payment page where the user can choose their
    preferred cryptocurrency and complete payment.

    Args:
        amount_usd: Amount in USD
        order_id: Unique order identifier (e.g., user_id + timestamp)
        order_description: Description shown on checkout page

    Returns:
        dict with invoice_url for redirect
    """
    try:
        credits, tier, rate = calculate_credits(amount_usd)
        payload = {
            "price_amount": amount_usd,
            "price_currency": "usd",
            "order_id": order_id,
            "order_description": f"{order_description} - {credits} credits ({tier} tier)",
            "ipn_callback_url": None,  # Uses dashboard-configured IPN URL
            "success_url": None,  # Will be set by frontend
            "cancel_url": None,
            "is_fixed_rate": True,
            "is_fee_paid_by_user": False
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{NOWPAYMENTS_API}/invoice",
                json=payload,
                headers=_headers()
            )
            data = resp.json()

            if "id" in data:
                data["credits_preview"] = credits
                data["tier"] = tier
                data["rate"] = f"{rate} credits/$1"
                data["invoice_url"] = data.get("invoice_url", f"https://nowpayments.io/payment/?iid={data["id"]}")

            return data
    except Exception as e:
        logger.error(f"Failed to create invoice: {e}")
        return {"error": str(e)}


async def create_payment(amount_usd: float, pay_currency: str, order_id: str) -> dict:
    """Create a direct payment (no hosted page, returns pay address).

    Use this for inline payment without redirect.
    """
    try:
        credits, tier, rate = calculate_credits(amount_usd)
        payload = {
            "price_amount": amount_usd,
            "price_currency": "usd",
            "pay_currency": pay_currency,
            "order_id": order_id,
            "order_description": f"OMEN Credits - {credits} credits",
            "is_fixed_rate": True,
            "is_fee_paid_by_user": False
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{NOWPAYMENTS_API}/payment",
                json=payload,
                headers=_headers()
            )
            data = resp.json()
            if "payment_id" in data:
                data["credits_preview"] = credits
                data["tier"] = tier
            return data
    except Exception as e:
        return {"error": str(e)}


async def get_payment_status(payment_id: str) -> dict:
    """Check payment status by payment ID."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{NOWPAYMENTS_API}/payment/{payment_id}",
                headers=_headers()
            )
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


def verify_ipn_signature(payload_body: bytes, received_signature: str) -> bool:
    """Verify NOWPayments IPN webhook signature.

    NOWPayments signs webhooks with HMAC-SHA512 using the IPN secret.
    """
    try:
        # NOWPayments: sort keys, then HMAC-SHA512
        data = json.loads(payload_body)
        sorted_data = json.dumps(data, sort_keys=True, separators=(",", ":"))
        expected_sig = hmac.new(
            NOWPAYMENTS_IPN_SECRET.encode(),
            sorted_data.encode(),
            hashlib.sha512
        ).hexdigest()
        return hmac.compare_digest(expected_sig, received_signature)
    except Exception as e:
        logger.error(f"IPN signature verification failed: {e}")
        return False


def process_ipn_data(data: dict) -> dict:
    """Process IPN webhook data and determine credit award.

    NOWPayments IPN statuses:
    - waiting, confirming, confirmed, sending, partially_paid, finished, failed, refunded, expired

    We only credit on 'finished' or 'confirmed'.
    """
    status = data.get("payment_status", "")
    order_id = data.get("order_id", "")
    payment_id = data.get("payment_id", "")
    price_amount = float(data.get("price_amount", 0))  # USD amount
    pay_amount = float(data.get("pay_amount", 0))  # Crypto amount paid
    actually_paid = float(data.get("actually_paid", 0))  # What was actually received
    pay_currency = data.get("pay_currency", "")
    outcome_amount = float(data.get("outcome_amount", 0))  # Final USD equivalent

    # Only credit on finished payments
    should_credit = status in ["finished", "confirmed"]

    credits = 0
    tier = ""
    rate = 0
    if should_credit and price_amount > 0:
        credits, tier, rate = calculate_credits(price_amount)

    return {
        "payment_id": payment_id,
        "order_id": order_id,
        "status": status,
        "should_credit": should_credit,
        "price_usd": price_amount,
        "pay_amount": pay_amount,
        "actually_paid": actually_paid,
        "pay_currency": pay_currency,
        "outcome_usd": outcome_amount,
        "credits": credits,
        "tier": tier,
        "rate": rate
    }


def get_payment_info() -> dict:
    """Return payment gateway info for frontend."""
    return {
        "gateway": "NOWPayments",
        "wallet": PAYMENT_WALLET,
        "supported_currencies": SUPPORTED_CURRENCIES,
        "credit_packages": [
            {"tier": "Starter", "price_usd": 5, "credits": 50, "rate": "10 credits/$1", "badge": "starter"},
            {"tier": "Popular", "price_usd": 10, "credits": 120, "rate": "12 credits/$1", "badge": "popular", "recommended": True},
            {"tier": "Pro", "price_usd": 20, "credits": 300, "rate": "15 credits/$1", "badge": "pro"},
            {"tier": "Whale", "price_usd": 50, "credits": 1000, "rate": "20 credits/$1", "badge": "whale"},
        ],
        "custom_amount": True,
        "min_amount_usd": 1,
        "max_amount_usd": 500
    }
