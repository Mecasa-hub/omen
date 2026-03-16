# OMEN — The Oracle Machine: API Reference

> **Version:** 1.0.0  
> **Base URL:** `https://omen.market/api`  
> **Protocol:** REST (JSON) + WebSocket  
> **Authentication:** Bearer JWT

---

## Table of Contents

1. [Authentication](#authentication)
2. [Error Handling](#error-handling)
3. [Rate Limiting](#rate-limiting)
4. [Auth Endpoints](#auth-endpoints)
5. [Credits Endpoints](#credits-endpoints)
6. [Oracle Endpoints](#oracle-endpoints)
7. [Whale Endpoints](#whale-endpoints)
8. [Trading Endpoints](#trading-endpoints)
9. [Chat Endpoints](#chat-endpoints)
10. [Social Endpoints](#social-endpoints)
11. [WebSocket Protocol](#websocket-protocol)
12. [Health & Status](#health--status)

---

## Authentication

All authenticated endpoints require a Bearer JWT token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

### Token Lifecycle

| Token Type | TTL | Usage |
|-----------|-----|-------|
| Access Token | 30 minutes | API authentication |
| Refresh Token | 7 days | Obtain new access token |

### Token Payload (JWT Claims)

```json
{
  "sub": "<user_uuid>",
  "exp": 1710000000,
  "type": "access"  // or "refresh"
}
```

**Algorithm:** HS256  
**Signing Key:** Configured via `JWT_SECRET` environment variable

---

## Error Handling

All errors return a consistent JSON structure:

```json
{
  "detail": "Human-readable error description"
}
```

### Standard HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `201` | Created |
| `400` | Bad Request — invalid input |
| `401` | Unauthorized — missing/invalid/expired token |
| `402` | Payment Required — insufficient credits |
| `403` | Forbidden — account deactivated |
| `404` | Not Found — resource doesn't exist |
| `409` | Conflict — duplicate resource (e.g., email already registered) |
| `422` | Unprocessable Entity — validation error |
| `500` | Internal Server Error — unexpected failure |

### Validation Error Format (422)

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

---

## Rate Limiting

| Endpoint Category | Limit | Window |
|-------------------|-------|--------|
| Auth (register/login) | 10 requests | per minute |
| Oracle predictions | 1 credit | per prediction |
| Trading execution | 30 requests | per minute |
| Whale leaderboard | 60 requests | per minute |
| Chat messages | 30 requests | per minute |
| Stripe webhooks | No limit | (signature verified) |

Rate limit headers (when Redis-backed limiting is enabled):

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 58
X-RateLimit-Reset: 1710000060
```

---

## Auth Endpoints

### POST /api/auth/register

Create a new user account.

**Authentication:** None

**Request Body:**

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `email` | string | ✅ | Valid email, max 320 chars | User email |
| `username` | string | ✅ | 3-64 chars, alphanumeric + underscore | Display name |
| `password` | string | ✅ | 8-128 chars | Account password |
| `referral_code` | string | ❌ | Max 16 chars | Referrer's code |

```json
{
  "email": "trader@example.com",
  "username": "oracle_trader",
  "password": "SecureP@ss123",
  "referral_code": "OMEN1234"
}
```

**Response:** `201 Created`

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "email": "trader@example.com",
  "username": "oracle_trader",
  "is_active": true,
  "credit_balance": 0,
  "referral_code": "XKCD9F2A",
  "created_at": "2026-03-16T12:00:00Z"
}
```

**Error Responses:**

| Code | Detail |
|------|--------|
| `409` | `"Email or username already registered"` |
| `400` | `"Invalid referral code"` |
| `422` | Validation errors |

**Example:**

```bash
curl -X POST https://omen.market/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "trader@example.com", "username": "oracle_trader", "password": "SecureP@ss123"}'
```

---

### POST /api/auth/login

Authenticate and receive JWT token pair.

**Authentication:** None

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `login` | string | ✅ | Email or username |
| `password` | string | ✅ | Account password |

```json
{
  "login": "oracle_trader",
  "password": "SecureP@ss123"
}
```

**Response:** `200 OK`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Error Responses:**

| Code | Detail |
|------|--------|
| `401` | `"Invalid credentials"` |
| `403` | `"Account deactivated"` |

**Example:**

```bash
curl -X POST https://omen.market/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"login": "oracle_trader", "password": "SecureP@ss123"}'
```

---

### GET /api/auth/me

Get the current authenticated user's profile.

**Authentication:** Required (Bearer JWT)

**Response:** `200 OK`

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "email": "trader@example.com",
  "username": "oracle_trader",
  "is_active": true,
  "credit_balance": 47,
  "referral_code": "XKCD9F2A",
  "created_at": "2026-03-16T12:00:00Z"
}
```

**Error Responses:**

| Code | Detail |
|------|--------|
| `401` | `"Invalid or expired token"` |
| `403` | `"Account deactivated"` |

**Example:**

```bash
curl https://omen.market/api/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### POST /api/auth/refresh

Exchange a valid refresh token for a new token pair.

**Authentication:** None (refresh token in body)

**Request Body:**

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:** `200 OK`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Error Responses:**

| Code | Detail |
|------|--------|
| `400` | `"refresh_token required"` |
| `401` | `"Invalid token type — refresh token required"` |
| `401` | `"User not found or inactive"` |

---

## Credits Endpoints

### GET /api/credits/balance

Get the current user's credit balance.

**Authentication:** Required

**Response:** `200 OK`

```json
{
  "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "balance": 47,
  "usd_equivalent": 4.70
}
```

**Example:**

```bash
curl https://omen.market/api/credits/balance \
  -H "Authorization: Bearer <token>"
```

---

### POST /api/credits/purchase

Purchase credits via Stripe. In dev mode, credits are added immediately.

**Authentication:** Required

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `amount_usd` | float | ✅ | Purchase amount in USD |

```json
{
  "amount_usd": 5.00
}
```

**Response:** `201 Created`

```json
{
  "id": "tx-uuid-here",
  "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "tx_type": "purchase",
  "amount": 50,
  "balance_after": 97,
  "description": "Purchase: $5.00 = 50 credits",
  "stripe_payment_id": "pi_dev_abc123",
  "created_at": "2026-03-16T12:05:00Z"
}
```

**Credit Conversion:** `$1 = 10 credits` → `$5 = 50 credits`

**Example:**

```bash
curl -X POST https://omen.market/api/credits/purchase \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"amount_usd": 5.00}'
```

---

### GET /api/credits/history

Get paginated credit transaction history.

**Authentication:** Required

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Results per page (1-100) |

**Response:** `200 OK`

```json
{
  "transactions": [
    {
      "id": "tx-uuid",
      "user_id": "user-uuid",
      "tx_type": "prediction",
      "amount": -1,
      "balance_after": 46,
      "description": "Prediction: Will BTC exceed $100K by March?",
      "stripe_payment_id": null,
      "metadata_json": {"market_id": "0x123..."},
      "created_at": "2026-03-16T12:10:00Z"
    }
  ],
  "total": 15,
  "page": 1,
  "page_size": 20
}
```

**Transaction Types:**

| Type | Description |
|------|-------------|
| `purchase` | Credits purchased via Stripe |
| `prediction` | Credit deducted for AI prediction |
| `trade_fee` | 2.5% platform fee on trades |
| `win_fee` | 5% profit-sharing fee |
| `referral_bonus` | 10% bonus from referee's purchase |
| `admin_adjustment` | Manual admin adjustment |

---

### POST /api/credits/webhook

Stripe webhook endpoint for payment completion events.

**Authentication:** Stripe signature verification

**Request:** Raw Stripe event payload

**Headers:**

```
stripe-signature: t=1710000000,v1=abc123...
Content-Type: application/json
```

**Handled Events:**

| Event | Action |
|-------|--------|
| `checkout.session.completed` | Add credits to user, process referral bonus |

**Response:** `200 OK`

```json
{"status": "processed"}
```

---

## Oracle Endpoints

### POST /api/oracle/predict

Create an AI prediction using the 5-agent debate engine.

**Authentication:** Required  
**Cost:** 1 credit

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `market_id` | string | ✅ | Polymarket market ID |
| `question` | string | ✅ | Market question |
| `context` | string | ❌ | Additional context for agents |

```json
{
  "market_id": "0x1234567890abcdef",
  "question": "Will Bitcoin exceed $100,000 by April 2026?",
  "context": "BTC currently at $95,000, strong momentum"
}
```

**Response:** `201 Created`

```json
{
  "id": "pred-uuid",
  "market_id": "0x1234567890abcdef",
  "question": "Will Bitcoin exceed $100,000 by April 2026?",
  "status": "completed",
  "verdict": {
    "direction": "YES",
    "confidence": 0.74,
    "agent_votes": [
      {
        "agent_name": "Atlas",
        "persona": "Data Analyst",
        "vote": "YES",
        "confidence": 0.72,
        "reasoning": "Historical momentum patterns suggest...",
        "weight": 1.0
      },
      {
        "agent_name": "Nemesis",
        "persona": "Devil's Advocate",
        "vote": "NO",
        "confidence": 0.65,
        "reasoning": "Resistance at $100K is significant...",
        "weight": 1.0
      },
      {
        "agent_name": "Quant",
        "persona": "Quantitative",
        "vote": "YES",
        "confidence": 0.81,
        "reasoning": "Monte Carlo simulations indicate...",
        "weight": 1.2
      },
      {
        "agent_name": "Maverick",
        "persona": "Contrarian",
        "vote": "YES",
        "confidence": 0.58,
        "reasoning": "Market sentiment is overly bearish...",
        "weight": 0.8
      },
      {
        "agent_name": "Clio",
        "persona": "Historian",
        "vote": "YES",
        "confidence": 0.69,
        "reasoning": "Previous cycles show post-halving rallies...",
        "weight": 1.0
      }
    ],
    "whale_alignment": 0.35,
    "final_confidence": 0.74,
    "reasoning_summary": "Verdict: YES at 74.0% confidence (whale alignment: +0.35)"
  },
  "created_at": "2026-03-16T12:00:00Z",
  "completed_at": "2026-03-16T12:00:08Z",
  "credits_used": 1
}
```

**Error Responses:**

| Code | Detail |
|------|--------|
| `402` | `"Insufficient credits: have 0, need 1"` |
| `500` | `"Prediction engine error: ..."` |

**Example:**

```bash
curl -X POST https://omen.market/api/oracle/predict \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"market_id": "0x123", "question": "Will BTC hit $100K?"}'
```

---

### GET /api/oracle/predictions

List the current user's predictions.

**Authentication:** Required

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number (≥1) |
| `page_size` | int | 20 | Results per page (1-100) |
| `market_id` | string | null | Filter by market ID |

**Response:** `200 OK`

```json
{
  "predictions": [
    {
      "id": "pred-uuid",
      "market_id": "0x123",
      "question": "Will BTC hit $100K?",
      "status": "completed",
      "verdict": { ... },
      "created_at": "2026-03-16T12:00:00Z",
      "completed_at": "2026-03-16T12:00:08Z",
      "credits_used": 1
    }
  ],
  "total": 12,
  "page": 1,
  "page_size": 20
}
```

---

### GET /api/oracle/prediction/{prediction_id}

Get a specific prediction by ID.

**Authentication:** Required

**Path Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `prediction_id` | UUID | Prediction ID |

**Response:** `200 OK` — Same structure as POST /predict response

**Error Responses:**

| Code | Detail |
|------|--------|
| `404` | `"Prediction not found"` |

**Example:**

```bash
curl https://omen.market/api/oracle/prediction/a1b2c3d4-... \
  -H "Authorization: Bearer <token>"
```

---

### WS /api/oracle/ws/debate

WebSocket endpoint for streaming live AI debates.

See [WebSocket Protocol — Debate](#debate-websocket) section below.

---

## Whale Endpoints

### GET /api/whale/leaderboard

Get the whale leaderboard ranked by specified metric.

**Authentication:** Required

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `sort_by` | string | `"roi"` | Sort metric: `roi`, `pnl`, `volume`, `win_rate`, `trades` |
| `limit` | int | 50 | Max results (1-200) |
| `offset` | int | 0 | Pagination offset |
| `active_only` | bool | true | Only show active wallets |

**Response:** `200 OK`

```json
{
  "whales": [
    {
      "id": "whale-uuid",
      "address": "0x1234...abcd",
      "label": "Theo4",
      "total_volume_usd": 2450000.00,
      "total_pnl_usd": 380000.00,
      "win_rate": 0.72,
      "roi_pct": 45.2,
      "num_trades": 342,
      "num_markets": 87,
      "is_active": true,
      "last_activity_at": "2026-03-16T11:30:00Z"
    }
  ],
  "total": 145,
  "sort_by": "roi",
  "limit": 50,
  "offset": 0
}
```

**Example:**

```bash
curl "https://omen.market/api/whale/leaderboard?sort_by=pnl&limit=20" \
  -H "Authorization: Bearer <token>"
```

---

### GET /api/whale/whale/{address}

Get a specific whale's profile by wallet address.

**Authentication:** Required

**Path Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `address` | string | Polygon wallet address |

**Response:** `200 OK`

```json
{
  "id": "whale-uuid",
  "address": "0x1234...abcd",
  "label": "Theo4",
  "total_volume_usd": 2450000.00,
  "total_pnl_usd": 380000.00,
  "win_rate": 0.72,
  "roi_pct": 45.2,
  "num_trades": 342,
  "num_markets": 87,
  "is_active": true,
  "last_activity_at": "2026-03-16T11:30:00Z",
  "discovered_at": "2026-01-15T08:00:00Z",
  "updated_at": "2026-03-16T11:35:00Z"
}
```

**Error Responses:**

| Code | Detail |
|------|--------|
| `404` | `"Whale wallet not found: 0x..."` |

---

### GET /api/whale/whale/{address}/positions

Get a whale's positions.

**Authentication:** Required

**Path Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `address` | string | Polygon wallet address |

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `open_only` | bool | true | Only show open positions |

**Response:** `200 OK`

```json
[
  {
    "id": "pos-uuid",
    "wallet_id": "whale-uuid",
    "market_id": "0xabc...",
    "market_question": "Will ETH reach $5,000 by Q2 2026?",
    "token_id": "71321...",
    "side": "YES",
    "size": 15000.0,
    "avg_price": 0.62,
    "current_price": 0.71,
    "pnl_usd": 1350.00,
    "is_open": true,
    "opened_at": "2026-03-10T14:00:00Z",
    "closed_at": null,
    "updated_at": "2026-03-16T11:30:00Z"
  }
]
```

---

### GET /api/whale/alerts

Get recent whale movement alerts.

**Authentication:** Required

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Max alerts (1-200) |

**Response:** `200 OK`

```json
{
  "alerts": [
    {
      "whale_address": "0x1234...abcd",
      "whale_label": "Theo4",
      "alert_type": "new_position",
      "market_id": "0xabc...",
      "market_question": "Will ETH reach $5,000?",
      "side": "YES",
      "size_usd": 25000.00,
      "price": 0.62,
      "timestamp": "2026-03-16T11:30:00Z"
    }
  ],
  "total": 42
}
```

---

## Trading Endpoints

### POST /api/trading/execute

Execute a trade on Polymarket.

**Authentication:** Required  
**Fees:** 2.5% of trade amount deducted as credits

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `market_id` | string | ✅ | Polymarket market ID |
| `token_id` | string | ✅ | CLOB token ID |
| `side` | string | ✅ | `"buy"` or `"sell"` |
| `amount_usd` | float | ✅ | Trade amount in USD |
| `price` | float | ✅ | Limit price (0.01 – 0.99) |
| `prediction_id` | UUID | ❌ | Link to a prediction |

```json
{
  "market_id": "0x1234567890abcdef",
  "token_id": "71321045663652420...",
  "side": "buy",
  "amount_usd": 50.00,
  "price": 0.65,
  "prediction_id": "pred-uuid-optional"
}
```

**Response:** `201 Created`

```json
{
  "id": "trade-uuid",
  "user_id": "user-uuid",
  "market_id": "0x123...",
  "token_id": "71321...",
  "side": "buy",
  "amount_usd": 50.00,
  "price": 0.65,
  "size": 76.92,
  "status": "placed",
  "order_id": "order_abc123",
  "fee_usd": 1.25,
  "pnl_usd": null,
  "is_copy_trade": false,
  "copy_source_wallet": null,
  "prediction_id": "pred-uuid",
  "created_at": "2026-03-16T12:00:00Z",
  "updated_at": "2026-03-16T12:00:00Z"
}
```

**Error Responses:**

| Code | Detail |
|------|--------|
| `400` | `"Risk check failed: ..."` |
| `402` | `"Insufficient credits for trade fee (13 credits)"` |

**Example:**

```bash
curl -X POST https://omen.market/api/trading/execute \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"market_id": "0x123", "token_id": "713...", "side": "buy", "amount_usd": 50, "price": 0.65}'
```

---

### GET /api/trading/positions

Get the current user's open positions.

**Authentication:** Required

**Response:** `200 OK`

```json
[
  {
    "id": "trade-uuid",
    "market_id": "0x123...",
    "token_id": "713...",
    "side": "buy",
    "amount_usd": 50.00,
    "price": 0.65,
    "size": 76.92,
    "status": "filled",
    "fee_usd": 1.25,
    "pnl_usd": 5.38,
    "is_copy_trade": false,
    "created_at": "2026-03-16T12:00:00Z"
  }
]
```

---

### GET /api/trading/history

Get paginated trade history.

**Authentication:** Required

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Results per page (1-100) |
| `market_id` | string | null | Filter by market |
| `side` | string | null | Filter: `"buy"` or `"sell"` |

**Response:** `200 OK`

```json
{
  "trades": [ ... ],
  "total": 87,
  "page": 1,
  "page_size": 20
}
```

---

### POST /api/trading/copy/start

Start copy-trading a whale wallet.

**Authentication:** Required

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `whale_address` | string | ✅ | — | Whale wallet to copy |
| `max_trade_usd` | float | ❌ | 100.0 | Max per-trade amount |
| `copy_percentage` | float | ❌ | 0.1 | Fraction of whale's position |
| `stop_loss_pct` | float | ❌ | 0.2 | Stop-loss threshold (20%) |
| `auto_exit` | bool | ❌ | true | Exit when whale exits |
| `markets_whitelist` | list | ❌ | null | Only copy these markets |
| `markets_blacklist` | list | ❌ | null | Never copy these markets |

```json
{
  "whale_address": "0x1234...abcd",
  "max_trade_usd": 50.00,
  "copy_percentage": 0.05,
  "stop_loss_pct": 0.15,
  "auto_exit": true
}
```

**Response:** `200 OK`

```json
{
  "status": "copy_session_started",
  "whale_address": "0x1234...abcd",
  "config": { ... }
}
```

---

### POST /api/trading/copy/stop

Stop copy-trading a whale wallet.

**Authentication:** Required

**Query Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `whale_address` | string | Whale wallet to stop copying |

**Response:** `200 OK`

```json
{
  "status": "copy_session_stopped",
  "whale_address": "0x1234...abcd"
}
```

---

## Chat Endpoints

### POST /api/chat/message

Send a message to the OMEN AI assistant.

**Authentication:** Required

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | ✅ | User's message |
| `context_market_id` | string | ❌ | Market context for the conversation |

```json
{
  "message": "What do the whales think about the ETH $5K market?",
  "context_market_id": "0xabc..."
}
```

**Response:** `200 OK`

```json
{
  "message": {
    "id": "msg-uuid",
    "user_id": "user-uuid",
    "role": "assistant",
    "content": "Based on whale tracker data, 3 of the top 5 whales by ROI have YES positions in this market...",
    "metadata_json": {"tokens_used": 450},
    "created_at": "2026-03-16T12:00:00Z"
  },
  "tokens_used": 450
}
```

**Example:**

```bash
curl -X POST https://omen.market/api/chat/message \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Analyze the BTC $100K market for me"}'
```

---

### GET /api/chat/history

Get paginated chat history.

**Authentication:** Required

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `page_size` | int | 50 | Results per page (1-200) |

**Response:** `200 OK`

```json
{
  "messages": [
    {
      "id": "msg-uuid",
      "user_id": "user-uuid",
      "role": "user",
      "content": "What do the whales think?",
      "created_at": "2026-03-16T12:00:00Z"
    },
    {
      "id": "msg-uuid-2",
      "user_id": "user-uuid",
      "role": "assistant",
      "content": "Based on whale tracker data...",
      "created_at": "2026-03-16T12:00:02Z"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 50
}
```

---

### DELETE /api/chat/clear

Clear all chat history for the current user.

**Authentication:** Required

**Response:** `200 OK`

```json
{
  "message": "Cleared 42 messages",
  "deleted": 42
}
```

---

### WS /api/chat/ws/chat

WebSocket endpoint for real-time chat.

See [WebSocket Protocol — Chat](#chat-websocket) section below.

---

## Social Endpoints

### POST /api/social/share

Share a prediction or trade to a social platform.

**Authentication:** Required

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content_type` | string | ✅ | `"prediction"` or `"trade"` |
| `content_id` | UUID | ✅ | ID of the content to share |
| `platform` | string | ✅ | `"twitter"`, `"telegram"`, `"link"` |
| `message` | string | ❌ | Custom share message |

```json
{
  "content_type": "prediction",
  "content_id": "pred-uuid",
  "platform": "twitter",
  "message": "OMEN predicted YES at 74% confidence! 🔮"
}
```

**Response:** `200 OK`

```json
{
  "share_url": "https://omen.market/prediction/pred-uuid",
  "platform": "twitter",
  "content_type": "prediction",
  "shared_at": "2026-03-16T12:00:00Z"
}
```

---

### GET /api/social/referral/code

Get or create a referral code for the current user.

**Authentication:** Required

**Response:** `200 OK`

```json
{
  "referral_code": "XKCD9F2A",
  "referral_url": "https://omen.market/register?ref=XKCD9F2A",
  "total_referrals": 5,
  "total_earned_credits": 75
}
```

---

### GET /api/social/referral/stats

Get referral program statistics.

**Authentication:** Required

**Response:** `200 OK`

```json
{
  "referral_code": "XKCD9F2A",
  "total_referrals": 5,
  "active_referrals": 4,
  "total_earned_credits": 75,
  "recent_referrals": [
    {
      "referee_username": "new_trader",
      "earned_credits": 5,
      "created_at": "2026-03-15T10:00:00Z"
    }
  ]
}
```

---

### POST /api/social/brag

Generate a shareable brag card for a trade or prediction win.

**Authentication:** Required

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `trade_id` | UUID | Conditional | Trade to brag about |
| `prediction_id` | UUID | Conditional | Prediction to brag about |
| `custom_message` | string | ❌ | Custom text on the card |

*At least one of `trade_id` or `prediction_id` is required.*

```json
{
  "prediction_id": "pred-uuid",
  "custom_message": "The Oracle sees all 🔮"
}
```

**Response:** `200 OK`

```json
{
  "card_id": "brag-uuid",
  "card_type": "prediction",
  "svg_content": "<svg>...</svg>",
  "image_url": "https://omen.market/brag/brag-uuid.png",
  "share_text": "🔮 OMEN predicted YES at 74% — The Oracle sees all!",
  "share_url": "https://omen.market/brag/brag-uuid"
}
```

---

## WebSocket Protocol

### Debate WebSocket

**URL:** `wss://omen.market/api/oracle/ws/debate`

#### Client → Server (Initial Request)

```json
{
  "question": "Will Bitcoin exceed $100,000 by April 2026?",
  "context": "Optional additional context",
  "token": "jwt_access_token_optional"
}
```

#### Server → Client (Events)

**Agent Speaking Event:**

```json
{
  "event": "agent_speaking",
  "agent_name": "Atlas",
  "persona": "Data Analyst",
  "content": "Looking at the historical data...",
  "timestamp": "2026-03-16T12:00:01Z"
}
```

**Agent Vote Event:**

```json
{
  "event": "agent_vote",
  "agent_name": "Atlas",
  "vote": "YES",
  "confidence": 0.72,
  "reasoning": "Statistical analysis supports upward momentum...",
  "timestamp": "2026-03-16T12:00:03Z"
}
```

**Debate Complete Event:**

```json
{
  "event": "debate_complete",
  "content": "All agents have voted. Debate complete.",
  "timestamp": "2026-03-16T12:00:08Z"
}
```

**Error Event:**

```json
{
  "event": "error",
  "content": "Missing question"
}
```

#### Connection Lifecycle

1. Client connects to WebSocket URL
2. Server accepts connection
3. Client sends initial request JSON
4. Server streams debate events (5 agents × 2 events each)
5. Server sends `debate_complete` event
6. Connection remains open (client can disconnect)

---

### Chat WebSocket

**URL:** `wss://omen.market/api/chat/ws/chat`

#### Client → Server (Message)

```json
{
  "message": "What's your take on the BTC market?",
  "token": "jwt_access_token",
  "context_market_id": "0x123..."
}
```

*Note: `token` is required on the first message for authentication.*

#### Server → Client (Events)

**Typing Indicator:**

```json
{
  "event": "typing",
  "content": "OMEN is thinking...",
  "timestamp": "2026-03-16T12:00:00Z"
}
```

**Response:**

```json
{
  "event": "response",
  "content": "Based on current market data and whale positions...",
  "tokens_used": 380,
  "timestamp": "2026-03-16T12:00:02Z"
}
```

**Error:**

```json
{
  "event": "error",
  "content": "Authentication required"
}
```

#### Connection Lifecycle

1. Client connects to WebSocket URL
2. Server accepts connection
3. Client sends message with JWT token
4. Server authenticates user (first message only)
5. Server sends typing indicator
6. Server sends response
7. Connection remains open for continued conversation
8. Client can send additional messages without re-authenticating

---

## Health & Status

### GET /

Root endpoint — basic service info.

**Authentication:** None

```json
{
  "service": "OMEN — The Oracle Machine",
  "version": "1.0.0",
  "status": "online",
  "docs": "/docs",
  "timestamp": "2026-03-16T12:00:00Z"
}
```

### GET /health

Comprehensive health check.

**Authentication:** None

```json
{
  "status": "healthy",
  "timestamp": "2026-03-16T12:00:00Z",
  "version": "1.0.0",
  "environment": "production",
  "checks": {
    "database": {"status": "up", "latency_ms": 2},
    "memory": {"rss_mb": 128.5, "vms_mb": 512.3},
    "routes": {"total": 28}
  }
}
```

### GET /api/status

API module availability.

**Authentication:** None

```json
{
  "status": "operational",
  "modules": {
    "auth": "available",
    "credits": "available",
    "oracle": "available",
    "whale": "available",
    "trading": "available",
    "chat": "available",
    "social": "available"
  },
  "features": {
    "ai_debate": true,
    "whale_tracking": true,
    "copy_trading": true,
    "brag_cards": true,
    "referrals": true,
    "websocket_debate": true,
    "websocket_chat": true
  }
}
```

---

## Interactive Documentation

OMEN provides auto-generated interactive API docs:

- **Swagger UI:** `https://omen.market/docs`
- **ReDoc:** `https://omen.market/redoc`
- **OpenAPI JSON:** `https://omen.market/openapi.json`
