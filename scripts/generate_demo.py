#!/usr/bin/env python3
"""OMEN — Generate Comprehensive Demo Data.

Creates realistic, internally consistent demo data across all tables:
- 5 demo users with hashed passwords
- Credit transactions for each user
- 20+ sample predictions with various outcomes
- 50+ sample trades
- Whale wallets and positions (delegates to seed_whales)
- Chat messages
- Referral codes and relationships

Usage:
    python scripts/generate_demo.py
"""

import asyncio
import logging
import random
import secrets
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend to Python path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("generate_demo")

# ═══════════════════════════════════════════════════════════════════
# Demo Data Definitions
# ═══════════════════════════════════════════════════════════════════

DEMO_USERS = [
    {
        "email": "alice@demo.omen.market",
        "username": "alice_oracle",
        "password": "DemoPass123!",
        "initial_credits": 150,
    },
    {
        "email": "bob@demo.omen.market",
        "username": "bob_trader",
        "password": "DemoPass123!",
        "initial_credits": 85,
    },
    {
        "email": "charlie@demo.omen.market",
        "username": "charlie_whale",
        "password": "DemoPass123!",
        "initial_credits": 320,
    },
    {
        "email": "diana@demo.omen.market",
        "username": "diana_degen",
        "password": "DemoPass123!",
        "initial_credits": 50,
    },
    {
        "email": "eve@demo.omen.market",
        "username": "eve_analyst",
        "password": "DemoPass123!",
        "initial_credits": 200,
    },
]

DEMO_MARKETS = [
    {
        "market_id": "0x" + "a1" * 20,
        "question": "Will Bitcoin exceed $100,000 by April 2026?",
        "token_id": "713210456636524203869" + "001",
    },
    {
        "market_id": "0x" + "b2" * 20,
        "question": "Will Ethereum reach $5,000 by Q2 2026?",
        "token_id": "713210456636524203869" + "002",
    },
    {
        "market_id": "0x" + "c3" * 20,
        "question": "Will the Fed cut rates in March 2026?",
        "token_id": "713210456636524203869" + "003",
    },
    {
        "market_id": "0x" + "d4" * 20,
        "question": "Will Apple release AR glasses in 2026?",
        "token_id": "713210456636524203869" + "004",
    },
    {
        "market_id": "0x" + "e5" * 20,
        "question": "Will SpaceX Starship complete orbital flight by Q2 2026?",
        "token_id": "713210456636524203869" + "005",
    },
    {
        "market_id": "0x" + "f6" * 20,
        "question": "Will the US pass a stablecoin bill in 2026?",
        "token_id": "713210456636524203869" + "006",
    },
    {
        "market_id": "0x" + "a7" * 20,
        "question": "Will global AI regulation be enacted by end of 2026?",
        "token_id": "713210456636524203869" + "007",
    },
    {
        "market_id": "0x" + "b8" * 20,
        "question": "Will SOL flip BNB in market cap by Q3 2026?",
        "token_id": "713210456636524203869" + "008",
    },
]

AGENT_PERSONAS = [
    {"agent_name": "Atlas", "persona": "Data Analyst", "weight": 1.0},
    {"agent_name": "Nemesis", "persona": "Devil's Advocate", "weight": 1.0},
    {"agent_name": "Quant", "persona": "Quantitative", "weight": 1.2},
    {"agent_name": "Maverick", "persona": "Contrarian", "weight": 0.8},
    {"agent_name": "Clio", "persona": "Historian", "weight": 1.0},
]

CHAT_CONVERSATIONS = [
    [
        ("user", "What do the whales think about BTC hitting $100K?"),
        ("assistant", "Based on whale tracker data, 4 of the top 5 whales by ROI currently hold YES positions on the BTC $100K market. The largest position is $150K at an entry price of $0.62. Whale alignment score is +0.35, indicating strong bullish sentiment among smart money."),
        ("user", "Should I follow them?"),
        ("assistant", "The whale consensus is bullish, but remember that whale alignment is just one signal. I'd recommend running an Oracle prediction first (costs 1 credit) to get the full 5-agent debate analysis. If both the Oracle and whale data agree, that's a much stronger signal. Would you like me to run a prediction?"),
    ],
    [
        ("user", "How does the copy trading work?"),
        ("assistant", "OMEN's copy-trading lets you mirror whale positions automatically. Here's how it works:\n\n1. **Choose a whale** from the leaderboard\n2. **Set your parameters**: max trade size, copy percentage, stop-loss\n3. **Start copying** — when the whale opens a position, we open a proportional one for you\n4. **Auto-exit** option closes your position when the whale exits\n\nFees: 2.5% on each trade + 5% on profits. You'll need sufficient credits for the trade fees."),
    ],
    [
        ("user", "Show me my recent predictions"),
        ("assistant", "Here are your last 5 predictions:\n\n✅ BTC > $100K — YES (74% confidence) — CORRECT\n✅ ETH > $5K — YES (68% confidence) — CORRECT\n❌ Fed rate cut March — YES (61% confidence) — WRONG\n✅ Apple AR glasses — NO (72% confidence) — CORRECT\n⏳ Starship orbital — YES (79% confidence) — PENDING\n\nYour prediction accuracy: 75% (3/4 resolved). Nice work!"),
    ],
]


async def generate_demo_data() -> None:
    """Generate all demo data in the database."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from auth.utils import hash_password
    from database import async_session_factory, engine
    from models import (
        ChatMessage,
        ChatRole,
        CreditTransaction,
        Prediction,
        PredictionStatus,
        Referral,
        Trade,
        TradeSide,
        TradeStatus,
        TransactionType,
        User,
    )

    logger.info("=" * 60)
    logger.info("  OMEN — Generate Demo Data")
    logger.info("=" * 60)

    now = datetime.now(timezone.utc)
    stats = {
        "users": 0,
        "credit_transactions": 0,
        "predictions": 0,
        "trades": 0,
        "chat_messages": 0,
        "referrals": 0,
    }

    async with async_session_factory() as session:  # type: AsyncSession
        # ── Create Users ──────────────────────────────────────────
        logger.info("Creating demo users...")
        user_objects = []

        for user_data in DEMO_USERS:
            # Check if already exists
            result = await session.execute(
                select(User).where(User.email == user_data["email"])
            )
            existing = result.scalar_one_or_none()
            if existing:
                logger.info("  ⏭️  User %s already exists", user_data["username"])
                user_objects.append(existing)
                continue

            referral_code = secrets.token_urlsafe(6)[:8].upper()
            user = User(
                email=user_data["email"],
                username=user_data["username"],
                hashed_password=hash_password(user_data["password"]),
                is_active=True,
                credit_balance=user_data["initial_credits"],
                referral_code=referral_code,
            )
            session.add(user)
            await session.flush()
            user_objects.append(user)
            stats["users"] += 1
            logger.info(
                "  ✅ Created user: %s (balance: %d credits, ref: %s)",
                user.username,
                user.credit_balance,
                user.referral_code,
            )

        # ── Create Referral Relationships ────────────────────────
        # alice referred bob, charlie referred diana
        logger.info("Creating referral relationships...")
        referral_pairs = [
            (0, 1),  # alice → bob
            (2, 3),  # charlie → diana
        ]
        for referrer_idx, referee_idx in referral_pairs:
            referrer = user_objects[referrer_idx]
            referee = user_objects[referee_idx]

            result = await session.execute(
                select(Referral).where(Referral.referee_id == referee.id)
            )
            if result.scalar_one_or_none():
                logger.info("  ⏭️  Referral %s→%s already exists", referrer.username, referee.username)
                continue

            ref = Referral(
                referrer_id=referrer.id,
                referee_id=referee.id,
                referral_code=referrer.referral_code,
                status="active",
                total_earned_credits=random.randint(5, 25),
            )
            session.add(ref)
            stats["referrals"] += 1
            # Update referred_by on referee
            referee.referred_by = referrer.id
            logger.info(
                "  ✅ Referral: %s → %s",
                referrer.username,
                referee.username,
            )

        # ── Create Credit Transactions ───────────────────────────
        logger.info("Creating credit transactions...")
        for user in user_objects:
            # Initial purchase
            purchase_amount = random.choice([5, 10, 25, 50])
            credits_granted = purchase_amount * 10
            tx = CreditTransaction(
                user_id=user.id,
                tx_type=TransactionType.PURCHASE,
                amount=credits_granted,
                balance_after=credits_granted,
                description=f"Purchase: ${purchase_amount:.2f} = {credits_granted} credits",
                stripe_payment_id=f"pi_dev_{uuid.uuid4().hex[:16]}",
                metadata_json={"amount_usd": purchase_amount, "rate": 10},
                created_at=now - timedelta(days=random.randint(7, 30)),
            )
            session.add(tx)
            stats["credit_transactions"] += 1

            # A few prediction deductions
            for i in range(random.randint(2, 6)):
                running_balance = credits_granted - (i + 1)
                tx = CreditTransaction(
                    user_id=user.id,
                    tx_type=TransactionType.PREDICTION,
                    amount=-1,
                    balance_after=max(0, running_balance),
                    description=f"Prediction: {random.choice(DEMO_MARKETS)['question'][:60]}",
                    created_at=now - timedelta(days=random.randint(1, 7), hours=random.randint(0, 23)),
                )
                session.add(tx)
                stats["credit_transactions"] += 1

            # A trade fee transaction
            fee_credits = random.randint(1, 13)
            tx = CreditTransaction(
                user_id=user.id,
                tx_type=TransactionType.TRADE_FEE,
                amount=-fee_credits,
                balance_after=max(0, user.credit_balance - fee_credits),
                description=f"Trade fee on ${random.uniform(10, 100):.2f} trade",
                created_at=now - timedelta(days=random.randint(1, 5)),
            )
            session.add(tx)
            stats["credit_transactions"] += 1

        # ── Create Predictions ───────────────────────────────────
        logger.info("Creating sample predictions...")
        for _ in range(25):
            user = random.choice(user_objects)
            market = random.choice(DEMO_MARKETS)
            status = random.choice([
                PredictionStatus.COMPLETED,
                PredictionStatus.COMPLETED,
                PredictionStatus.COMPLETED,
                PredictionStatus.PENDING,
                PredictionStatus.FAILED,
            ])
            verdict_dir = random.choice(["YES", "NO"])
            confidence = round(random.uniform(0.55, 0.92), 4)

            # Build agent votes
            votes = []
            for agent in AGENT_PERSONAS:
                agent_vote = random.choice(["YES", "NO"])
                votes.append({
                    "agent_name": agent["agent_name"],
                    "persona": agent["persona"],
                    "vote": agent_vote,
                    "confidence": round(random.uniform(0.45, 0.90), 4),
                    "reasoning": f"{agent['agent_name']} analysis of {market['question'][:40]}...",
                    "weight": agent["weight"],
                })

            created_at = now - timedelta(
                days=random.randint(0, 14),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )

            prediction = Prediction(
                user_id=user.id,
                market_id=market["market_id"],
                question=market["question"],
                status=status,
                verdict=verdict_dir if status == PredictionStatus.COMPLETED else None,
                confidence=confidence if status == PredictionStatus.COMPLETED else None,
                debate_log={"agents": votes, "rounds": 1} if status == PredictionStatus.COMPLETED else None,
                agent_votes={"votes": votes} if status == PredictionStatus.COMPLETED else None,
                whale_alignment=round(random.uniform(-0.5, 0.5), 4) if status == PredictionStatus.COMPLETED else None,
                created_at=created_at,
                completed_at=created_at + timedelta(seconds=random.randint(5, 30)) if status == PredictionStatus.COMPLETED else None,
            )
            session.add(prediction)
            stats["predictions"] += 1

        # ── Create Trades ────────────────────────────────────────
        logger.info("Creating sample trades...")
        for _ in range(55):
            user = random.choice(user_objects)
            market = random.choice(DEMO_MARKETS)
            side = random.choice([TradeSide.BUY, TradeSide.SELL])
            amount_usd = round(random.uniform(5.0, 200.0), 2)
            price = round(random.uniform(0.20, 0.85), 4)
            size = round(amount_usd / price, 4)
            status = random.choice([
                TradeStatus.FILLED,
                TradeStatus.FILLED,
                TradeStatus.FILLED,
                TradeStatus.PLACED,
                TradeStatus.CANCELLED,
                TradeStatus.PARTIALLY_FILLED,
            ])
            fee = round(amount_usd * 0.025, 4)
            pnl = round(random.uniform(-50, 80), 2) if status == TradeStatus.FILLED else None
            is_copy = random.random() < 0.2  # 20% are copy trades

            created_at = now - timedelta(
                days=random.randint(0, 14),
                hours=random.randint(0, 23),
            )

            trade = Trade(
                user_id=user.id,
                market_id=market["market_id"],
                token_id=market["token_id"],
                side=side,
                amount_usd=amount_usd,
                price=price,
                size=size,
                status=status,
                order_id=f"order_{uuid.uuid4().hex[:12]}" if status != TradeStatus.CANCELLED else None,
                fee_usd=fee,
                pnl_usd=pnl,
                is_copy_trade=is_copy,
                copy_source_wallet="0xB7c6EC08bC5A7F8E2cc25b14bBA1f6D3b8d9cE10" if is_copy else None,
                created_at=created_at,
            )
            session.add(trade)
            stats["trades"] += 1

        # ── Create Chat Messages ─────────────────────────────────
        logger.info("Creating chat messages...")
        for i, user in enumerate(user_objects[:3]):  # First 3 users get chat history
            if i < len(CHAT_CONVERSATIONS):
                conversation = CHAT_CONVERSATIONS[i]
                base_time = now - timedelta(hours=random.randint(1, 48))

                for j, (role_str, content) in enumerate(conversation):
                    role = ChatRole.USER if role_str == "user" else ChatRole.ASSISTANT
                    msg = ChatMessage(
                        user_id=user.id,
                        role=role,
                        content=content,
                        metadata_json=(
                            {"tokens_used": random.randint(100, 500)}
                            if role == ChatRole.ASSISTANT
                            else None
                        ),
                        created_at=base_time + timedelta(seconds=j * 30),
                    )
                    session.add(msg)
                    stats["chat_messages"] += 1

        # ── Commit Everything ────────────────────────────────────
        await session.commit()

    logger.info("")
    logger.info("Demo data generation complete:")
    for table, count in stats.items():
        logger.info("  %-25s %d records", table, count)
    logger.info("")
    logger.info("Demo login credentials:")
    for u in DEMO_USERS:
        logger.info("  %s / %s / %s", u["email"], u["username"], u["password"])

    await engine.dispose()


def main() -> None:
    """Entry point."""
    try:
        asyncio.run(generate_demo_data())
    except KeyboardInterrupt:
        logger.info("Generation interrupted.")
        sys.exit(1)
    except Exception as exc:
        logger.error("Generation failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
