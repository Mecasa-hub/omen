# OMEN — The Oracle Machine: Credit System

> **Version:** 1.0.0  
> **Last Updated:** 2026-03-16  
> **Model:** Pay-as-you-go credits

---

## Table of Contents

1. [Overview](#overview)
2. [Credit Pricing](#credit-pricing)
3. [Credit Consumption](#credit-consumption)
4. [Trade Fees](#trade-fees)
5. [Referral Bonuses](#referral-bonuses)
6. [Stripe Integration](#stripe-integration)
7. [Credit Lifecycle](#credit-lifecycle)
8. [Anti-Abuse Measures](#anti-abuse-measures)
9. [Transaction Types](#transaction-types)
10. [API Reference](#api-reference)
11. [Future Plans](#future-plans)

---

## Overview

OMEN uses a **pay-as-you-go credit system** that provides transparent, predictable costs. Users purchase credits in advance and spend them on AI predictions and trading fees. This model ensures:

- **No subscriptions** — pay only for what you use
- **No surprise charges** — see credit costs before every action
- **Transparent pricing** — fixed conversion rate, no hidden fees
- **Instant access** — credits available immediately after purchase

---

## Credit Pricing

### Base Rate

| Purchase | Credits | Rate |
|----------|---------|------|
| **$5.00** | **50 credits** | **$0.10 / credit** |
| $10.00 | 100 credits | $0.10 / credit |
| $25.00 | 250 credits | $0.10 / credit |
| $50.00 | 500 credits | $0.10 / credit |
| $100.00 | 1,000 credits | $0.10 / credit |

**Conversion Formula:** `credits = amount_usd × 10`

The minimum purchase is **$5.00 (50 credits)**.

### What Can You Do with 50 Credits?

| Action | Cost | Count with 50 Credits |
|--------|------|-----------------------|
| AI Prediction | 1 credit | 50 predictions |
| $10 Trade Fee | ~3 credits | ~16 trades |
| $50 Trade Fee | ~13 credits | ~3 trades |
| $100 Trade Fee | ~25 credits | 2 trades |

---

## Credit Consumption

### AI Predictions

**Cost: 1 credit per prediction**

Each prediction query runs the full 5-agent Oracle debate engine:

1. **Atlas** (Data Analyst) analyzes statistical data
2. **Nemesis** (Devil's Advocate) challenges assumptions
3. **Quant** (Quantitative) runs mathematical models
4. **Maverick** (Contrarian) offers alternative perspectives
5. **Clio** (Historian) checks historical precedents

The credit is deducted **before** the debate begins. If the debate fails (engine error), the prediction is marked as `failed` — the credit is still consumed as the AI agents attempted the analysis.

### Credit Deduction Flow

```
User clicks "Predict"  ──────►  Check balance ≥ 1
                                      │
                                ┌─────▼─────┐
                                │  Balance   │
                                │  ≥ 1?     │
                                └─────┬─────┘
                                  YES │    NO → 402 Error
                                      │
                                ┌─────▼─────┐
                                │  Deduct 1  │
                                │  credit    │
                                └─────┬─────┘
                                      │
                                ┌─────▼─────┐
                                │  Run 5-AI  │
                                │  Debate    │
                                └─────┬─────┘
                                      │
                                ┌─────▼─────┐
                                │  Return    │
                                │  Verdict   │
                                └────────────┘
```

---

## Trade Fees

OMEN charges two types of fees on trades executed through the platform:

### Execution Fee: 1%

Charged on **every trade** at the time of execution.

| Trade Amount | Fee (1%) | Fee in Credits |
|-------------|------------|----------------|
| $10.00 | $0.25 | 3 credits |
| $25.00 | $0.625 | 7 credits |
| $50.00 | $1.25 | 13 credits |
| $100.00 | $1.00 | 10 credits |
| $500.00 | $5.00 | 50 credits |

**Formula:** `fee_credits = max(1, int(amount_usd × 0.01 × 10))`

The fee is deducted from the user's credit balance as a `trade_fee` transaction. Minimum fee is 1 credit.

### Profit Fee: 1%

Charged **only on winning trades** when profits are realized.

| Profit | Fee (1%) | Fee in Credits |
|--------|----------|----------------|
| $10.00 | $0.50 | 5 credits |
| $50.00 | $0.50 | 5 credits |
| $100.00 | $5.00 | 50 credits |
| $500.00 | $25.00 | 250 credits |

**Formula:** `fee_credits = max(1, int(profit_usd × 0.01 × 10))` (only if profit > 0)

The profit fee is recorded as a `win_fee` transaction.

### Combined Fee Example

```
Trade: BUY $100 on "BTC > $100K" at 0.65
├── Execution fee: $100 × 1% = $1.00 (10 credits)
├── Market resolves YES → Payout: $100 / 0.65 = $153.85
├── Profit: $153.85 - $100 = $53.85
├── Profit fee: $53.85 × 1% = $0.54 (6 credits)
└── Total fees: 52 credits ($5.19)
    Net profit: $53.85 - $5.19 = $48.66
```

---

## Referral Bonuses

### How It Works

Every OMEN user receives a unique referral code (e.g., `XKCD9F2A`). When someone registers with your code and purchases credits, you earn **10% of their purchase** as bonus credits.

### Referral Flow

```
New User signs up with code "XKCD9F2A"
          │
          ▼
New User purchases $5.00 (50 credits)
          │
          ├──► New User receives: 50 credits
          │
          └──► Referrer receives: 5 bonus credits (10%)
              (recorded as referral_bonus transaction)
```

### Referral Rules

| Rule | Detail |
|------|--------|
| Bonus rate | 10% of every credit purchase by referee |
| Minimum bonus | 1 credit per qualifying purchase |
| Duration | Lifetime — no expiration on the referral bond |
| Self-referral | Not allowed (same email/IP detection) |
| Max referrals | Unlimited |
| Bonus type | Credits only (not withdrawable as cash) |

### Example Earnings

If you refer 10 users, and each spends $20/month:

```
10 users × $20/month × 10% = $20/month in bonus credits
= 200 bonus credits/month
= 200 free predictions or significant trade fee coverage
```

---

## Stripe Integration

### Payment Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  OMEN    │     │  Stripe  │     │  Stripe  │     │  OMEN    │
│ Frontend │     │ Checkout │     │ Webhook  │     │ Backend  │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │
     │ 1. Click Buy   │                │                │
     ├───────────────►│                │                │
     │                │                │                │
     │ 2. Redirect to │                │                │
     │    Checkout     │                │                │
     │◄───────────────┤                │                │
     │                │                │                │
     │ 3. User pays   │                │                │
     ├───────────────►│                │                │
     │                │                │                │
     │                │ 4. Webhook:    │                │
     │                │    checkout.   │                │
     │                │    session.    │                │
     │                │    completed   │                │
     │                │────────────────►                │
     │                │                │                │
     │                │                │ 5. Verify sig  │
     │                │                │ 6. Find user   │
     │                │                │ 7. Add credits │
     │                │                │ 8. Referral?   │
     │                │                │    → +10% bonus│
     │                │                │                │
     │ 9. Balance     │                │                │
     │    updated     │◄───────────────────────────────┤
     │                │                │                │
```

### Stripe Configuration

| Setting | Value |
|---------|-------|
| Product | "OMEN Credits" |
| Price | $5.00 per unit (50 credits) |
| Mode | Payment (one-time) |
| Webhook Event | `checkout.session.completed` |
| Webhook URL | `https://omen.market/api/credits/webhook` |
| Signature Verification | Yes (production) |

### Dev Mode

When `STRIPE_SECRET_KEY` is empty or set to a test key, the `/api/credits/purchase` endpoint grants credits immediately with a mock payment ID (`pi_dev_*`). No actual Stripe checkout occurs.

---

## Credit Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                     CREDIT LIFECYCLE                         │
│                                                             │
│  ┌──────────┐    ┌─────────────┐    ┌────────────────────┐ │
│  │ PURCHASE  │───►│ BALANCE     │───►│ CONSUMPTION         │ │
│  │ (+credits)│    │ (user.credit│    │                    │ │
│  │           │    │  _balance)  │    │ • Prediction (-1)  │ │
│  └──────────┘    └──────┬──────┘    │ • Trade fee (-N)   │ │
│                         │           │ • Win fee (-N)     │ │
│  ┌──────────┐           │           └────────────────────┘ │
│  │ REFERRAL  │──────────┘                                   │
│  │ BONUS     │                                              │
│  │ (+credits)│    Every mutation creates an immutable       │
│  └──────────┘    CreditTransaction ledger entry             │
│                                                             │
│  ┌──────────┐                                               │
│  │  ADMIN    │──────────► Direct balance adjustment          │
│  │ ADJUST    │            (for support/disputes)             │
│  └──────────┘                                               │
└─────────────────────────────────────────────────────────────┘
```

### Concurrency Safety

All balance mutations use `SELECT FOR UPDATE` to prevent race conditions:

```python
# Lock the user row before modifying balance
result = await session.execute(
    select(User).where(User.id == user_id).with_for_update()
)
user = result.scalar_one()
user.credit_balance += amount  # Atomic update
```

This ensures that concurrent requests (e.g., two predictions at the same time) cannot cause double-spending.

---

## Anti-Abuse Measures

### Rate Limiting

| Measure | Detail |
|---------|--------|
| Purchase rate | Max 10 purchases per hour per user |
| Prediction rate | Max 60 predictions per hour per user |
| Minimum purchase | $5.00 (prevents micro-transaction abuse) |
| Stripe deduplication | `stripe_payment_id` uniqueness check |

### Fraud Prevention

| Measure | Detail |
|---------|--------|
| Webhook verification | Stripe signature validation in production |
| Balance integrity | `balance_after` column in every transaction |
| Ledger immutability | `credit_transactions` table is append-only |
| Audit trail | All mutations logged with user_id, type, timestamp |
| Negative balance prevention | Balance checked before deduction with row lock |

### Reconciliation

The `balance_after` column on each `CreditTransaction` creates an auditable chain. To verify integrity:

```sql
-- Verify balance chain integrity for a user
SELECT id, tx_type, amount, balance_after,
       LAG(balance_after) OVER (ORDER BY created_at) as prev_balance,
       balance_after - LAG(balance_after) OVER (ORDER BY created_at) as computed_amount
FROM credit_transactions
WHERE user_id = '<uuid>'
ORDER BY created_at;

-- Alert: rows where computed_amount ≠ amount indicate corruption
```

---

## Transaction Types

| Type | Direction | Trigger | Description |
|------|-----------|---------|-------------|
| `purchase` | + (credit) | Stripe payment | User bought credits |
| `prediction` | - (debit) | POST /oracle/predict | AI prediction consumed |
| `trade_fee` | - (debit) | POST /trading/execute | 1% execution fee |
| `win_fee` | - (debit) | Trade profit realized | 1% profit sharing |
| `referral_bonus` | + (credit) | Referee purchases | 10% of referee's purchase |
| `admin_adjustment` | ± | Admin action | Manual correction/dispute resolution |

---

## API Reference

### Check Balance

```bash
GET /api/credits/balance
Authorization: Bearer <token>

# Response
{"user_id": "uuid", "balance": 47, "usd_equivalent": 4.70}
```

### Purchase Credits

```bash
POST /api/credits/purchase
Authorization: Bearer <token>
Content-Type: application/json

{"amount_usd": 5.00}

# Response (201)
{"id": "tx-uuid", "amount": 50, "balance_after": 97, ...}
```

### Transaction History

```bash
GET /api/credits/history?page=1&page_size=20
Authorization: Bearer <token>

# Response
{"transactions": [...], "total": 15, "page": 1, "page_size": 20}
```

See [API.md](./API.md) for complete endpoint documentation.

---

## Future Plans

### Credit Packages (Planned)

| Package | Credits | Price | Savings |
|---------|---------|-------|---------|
| Starter | 50 | $5.00 | — |
| Explorer | 200 | $18.00 | 10% off |
| Trader | 500 | $40.00 | 20% off |
| Whale | 2,000 | $140.00 | 30% off |
| Oracle | 10,000 | $600.00 | 40% off |

### Volume Discounts (Planned)

- Users who spend >$100/month get automatic 10% bonus credits
- Users who spend >$500/month get automatic 20% bonus credits
- Top referrers get elevated bonus rates (15-20%)

### Subscription Tiers (Under Consideration)

| Tier | Price/mo | Credits/mo | Perks |
|------|----------|------------|-------|
| Free | $0 | 5 free predictions | Basic access |
| Pro | $29/mo | 350 credits | Priority AI, whale alerts |
| Elite | $99/mo | 1,500 credits | Reduced fees (0.5%), API access |

### Credit Gifting (Planned)

- Users can gift credits to other users
- Credits can be earned through engagement (community challenges)

### Credit Expiration Policy (Under Review)

- Currently: Credits never expire
- Proposed: Credits expire after 365 days of account inactivity
- Grace period: 30-day warning before expiration


## Free Tier

Every new OMEN account includes:
- **50 welcome credits** to explore all features
- **10 free AI chat messages** to talk with your personal oracle
- **1 free daily prediction** — ask the Oracle one question per day, no credits needed

After your free messages are used, each AI chat message costs **1 credit**.
