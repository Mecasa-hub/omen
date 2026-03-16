# OMEN — The Oracle Machine: System Architecture

> **Version:** 1.0.0  
> **Last Updated:** 2026-03-16  
> **Status:** Production-Ready

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Component Breakdown](#component-breakdown)
4. [Data Flow](#data-flow)
5. [Database Schema](#database-schema)
6. [API Architecture](#api-architecture)
7. [Security Model](#security-model)
8. [Scaling Strategy](#scaling-strategy)
9. [Technology Decisions](#technology-decisions)

---

## System Overview

OMEN is an AI-powered Polymarket prediction and copy-trading SaaS platform that combines swarm intelligence debates with whale wallet tracking to deliver high-confidence market predictions. The platform operates on a credit-based revenue model with trade execution fees (1%) and profit-sharing (1%).

### Key Capabilities

| Feature | Description |
|---------|-------------|
| **Oracle Engine** | 5-agent AI debate system producing weighted consensus verdicts |
| **Whale Tracker** | Real-time monitoring of top Polymarket wallets with position alerts |
| **Copy Trading** | Mirror whale positions with configurable risk parameters |
| **AI Chat** | Per-user conversational assistant with market context |
| **Brag Cards** | Auto-generated SVG win cards for social sharing |
| **Referral System** | 10% credit bonus on referee purchases |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CLIENTS                                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │ Vue 3 SPA│  │ Mobile   │  │ X/Twitter│  │ API Users│               │
│  │ Frontend │  │ (Future) │  │   Bot    │  │ (curl)   │               │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘               │
│       │              │              │              │                    │
│       └──────────────┴──────────────┴──────────────┘                    │
│                              │                                          │
│                     ┌────────▼────────┐                                 │
│                     │   Nginx / CDN   │                                 │
│                     │  (SSL Termination)│                               │
│                     └────────┬────────┘                                 │
└──────────────────────────────┼──────────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────────┐
│                      FASTAPI APPLICATION                                │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                     API Gateway Layer                           │    │
│  │  ┌──────┐ ┌────────┐ ┌────────┐ ┌───────┐ ┌────────┐ ┌──────┐│    │
│  │  │ Auth │ │Credits │ │ Oracle │ │ Whale │ │Trading │ │ Chat ││    │
│  │  │Router│ │ Router │ │ Router │ │Router │ │ Router │ │Router││    │
│  │  └──┬───┘ └───┬────┘ └───┬────┘ └──┬────┘ └───┬────┘ └──┬───┘│    │
│  │     │         │          │         │          │         │     │    │
│  │  ┌──▼───┐ ┌───▼────┐ ┌──▼─────┐┌──▼────┐ ┌───▼────┐┌──▼───┐│    │
│  │  │ Auth │ │Credit  │ │Debate  ││Tracker│ │Executor││ Agent ││    │
│  │  │Utils │ │Service │ │Simultr ││Discvry│ │CopyEng ││ Chat  ││    │
│  │  └──────┘ └────────┘ │Verdict ││Leader ││RiskMgr │└───────┘│    │
│  │                      └────────┘└───────┘└────────┘         │    │
│  └─────────────────────────────────────────────────────────────┘    │
│  ┌──────────┐                                     ┌──────────┐      │
│  │  Social  │                                     │ WebSocket│      │
│  │  Router  │                                     │ Endpoints│      │
│  │ BragCards│                                     │ /ws/debate│     │
│  │ Referral │                                     │ /ws/chat  │     │
│  │ XBot     │                                     └──────────┘      │
│  └──────────┘                                                       │
└────────────┬────────────────────────────┬───────────────────────────┘
             │                            │
    ┌────────▼────────┐          ┌────────▼────────┐
    │   PostgreSQL    │          │     Redis       │
    │  (asyncpg)      │          │  (Cache/PubSub) │
    │                 │          │                 │
    │  • users        │          │  • Session cache│
    │  • predictions  │          │  • Rate limits  │
    │  • trades       │          │  • Alert PubSub │
    │  • whale_wallets│          │  • WS channels  │
    │  • chat_messages│          └─────────────────┘
    │  • referrals    │
    │  • credit_txns  │
    └────────┬────────┘
             │
    ┌────────▼─────────────────────────────────────────────┐
    │              EXTERNAL SERVICES                        │
    │                                                       │
    │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
    │  │  Polymarket  │  │  OpenRouter  │  │   Stripe    │ │
    │  │  CLOB API    │  │  (LLM API)   │  │  Payments   │ │
    │  │  Gamma API   │  │  Gemini 2.0  │  │  Webhooks   │ │
    │  │  WebSocket   │  │  Flash       │  │             │ │
    │  └──────────────┘  └──────────────┘  └─────────────┘ │
    │  ┌──────────────┐  ┌──────────────┐                  │
    │  │ Polygon RPC  │  │  X/Twitter   │                  │
    │  │ (Chain Data) │  │  API v2      │                  │
    │  └──────────────┘  └──────────────┘                  │
    └──────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. Backend (FastAPI)

**Entry Point:** `backend/main.py`  
**Framework:** FastAPI with async/await throughout  
**Server:** Uvicorn with lifespan context management

The backend is a modular FastAPI application organized into seven domain modules, each with its own router, schemas, and service logic:

| Module | Prefix | Purpose |
|--------|--------|---------|
| `auth` | `/api/auth` | User registration, login, JWT token management |
| `credits` | `/api/credits` | Credit balance, purchases, transaction history, Stripe webhooks |
| `oracle` | `/api/oracle` | AI predictions, debate engine, live WebSocket debates |
| `whale` | `/api/whale` | Whale leaderboard, profiles, positions, alerts, discovery |
| `trading` | `/api/trading` | Trade execution, positions, history, copy-trading |
| `chat` | `/api/chat` | AI assistant messages, history, WebSocket live chat |
| `social` | `/api/social` | Sharing, brag cards, referral codes, X/Twitter integration |

**Middleware:**
- CORS (configurable origins)
- Global exception handler (returns clean JSON errors)

**Lifecycle:**
- **Startup:** Verifies database connectivity, logs configuration
- **Shutdown:** Disposes database connection pool

### 2. Frontend (Vue 3 SPA)

**Framework:** Vue 3 with Composition API  
**Build Tool:** Vite  
**Styling:** Tailwind CSS v3  
**State:** Pinia stores  
**Routing:** Vue Router 4  
**HTTP:** Axios with JWT interceptors

**Key Views:**
- **Dashboard** — Portfolio overview, recent predictions, active positions
- **Oracle / War Room** — AI debate interface with live WebSocket streaming
- **Whale Board** — Leaderboard, whale profiles, position tracking
- **AutoPilot** — Copy-trading configuration and monitoring
- **Chat** — Conversational AI assistant with market context

### 3. Oracle Engine

**Location:** `backend/oracle/`  
**Files:** `swarm_engine.py`, `debate_simulator.py`, `verdict.py`

The Oracle Engine is a 5-agent AI debate system where specialized personas analyze market questions from different angles:

| Agent | Persona | Weight | Specialty |
|-------|---------|--------|-----------|
| **Atlas** | Data Analyst | 1.0 | Statistical analysis, historical data |
| **Nemesis** | Devil's Advocate | 1.0 | Counter-arguments, risk identification |
| **Quant** | Quantitative | 1.2 | Mathematical models, probability theory |
| **Maverick** | Contrarian | 0.8 | Unconventional perspectives, sentiment |
| **Clio** | Historian | 1.0 | Historical precedents, pattern matching |

**Debate Flow:**
1. User submits question + market context
2. Each agent generates independent analysis via OpenRouter (Gemini 2.0 Flash)
3. Agents vote YES/NO with confidence scores and reasoning
4. Weighted consensus calculated across all agents
5. Whale alignment score adjusts final confidence
6. Verdict returned: direction, confidence, agent votes, reasoning summary

### 4. Whale Tracker

**Location:** `backend/whale/`  
**Files:** `tracker.py`, `discovery.py`, `leaderboard.py`

- **Discovery:** Queries Polymarket's Gamma/Profile APIs to find high-performing wallets
- **Tracking:** Monitors position changes across all tracked wallets
- **Leaderboard:** Ranks whales by ROI, PnL, volume, win rate
- **Alerts:** Generates alerts when whales open/close significant positions

### 5. Trading Engine

**Location:** `backend/trading/`  
**Files:** `executor.py`, `copy_engine.py`, `risk_manager.py`

- **Executor:** Places orders via Polymarket CLOB API
- **Risk Manager:** Enforces per-trade limits, daily loss limits, and position sizing
- **Copy Engine:** Mirrors whale positions with configurable parameters:
  - `max_trade_usd` — Maximum per-trade amount
  - `copy_percentage` — Fraction of whale's position to mirror
  - `stop_loss_pct` — Automatic stop-loss threshold
  - `auto_exit` — Exit when whale exits
  - Market whitelist/blacklist filters

### 6. Chat Agent

**Location:** `backend/chat/`  
**Files:** `agent.py`

- Per-user conversational AI assistant
- Context-aware: can reference market data, user positions, predictions
- Persistent message history in database
- Available via REST (`POST /api/chat/message`) and WebSocket (`/api/chat/ws/chat`)

### 7. Social Module

**Location:** `backend/social/`  
**Files:** `brag_cards.py`, `referral.py`, `twitter_bot.py`

- **Brag Cards:** SVG generation for prediction/trade wins
- **Referral System:** Unique `OMEN-XXXX` codes with 10% bonus on referee purchases
- **X/Twitter Bot:** Posts whale alerts and user brag cards

---

## Data Flow

### Prediction Flow

```
User Request                     Oracle Engine                  Database
    │                                │                              │
    │  POST /api/oracle/predict      │                              │
    ├───────────────────────────────►│                              │
    │                                │  1. Deduct 1 credit          │
    │                                ├─────────────────────────────►│
    │                                │                              │
    │                                │  2. Create prediction (PENDING)
    │                                ├─────────────────────────────►│
    │                                │                              │
    │                                │  3. Run 5-agent debate       │
    │                                │  ┌──────────────────┐       │
    │                                │  │ Atlas  → YES 72% │       │
    │                                │  │ Nemesis→ NO  65% │       │
    │                                │  │ Quant  → YES 81% │       │
    │                                │  │ Maverick→YES 58% │       │
    │                                │  │ Clio   → YES 69% │       │
    │                                │  └──────────────────┘       │
    │                                │                              │
    │                                │  4. Calculate whale alignment│
    │                                │  5. Build weighted verdict   │
    │                                │                              │
    │                                │  6. Update prediction (DONE) │
    │                                ├─────────────────────────────►│
    │                                │                              │
    │  ◄──── Verdict Response ───────┤                              │
    │  {direction, confidence,       │                              │
    │   agent_votes, whale_alignment}│                              │
```

### Trade Execution Flow

```
User Request          Risk Manager       Credits         Polymarket CLOB
    │                     │                 │                    │
    │  POST /execute      │                 │                    │
    ├────────────────────►│                 │                    │
    │                     │  Check limits   │                    │
    │                     ├────────┐       │                    │
    │                     │        │       │                    │
    │                     │◄───────┘       │                    │
    │                     │  PASS           │                    │
    │                     │                 │                    │
    │                     │  Calc 1% fee  │                    │
    │                     ├────────────────►│                    │
    │                     │                 │  Deduct fee credits│
    │                     │                 ├───────┐           │
    │                     │                 │◄──────┘           │
    │                     │                 │                    │
    │                     │  Place order    │                    │
    │                     ├────────────────────────────────────►│
    │                     │                 │                    │
    │                     │  ◄── Order confirmation ────────────┤
    │                     │                 │                    │
    │  ◄── Trade Response─┤                 │                    │
```

### Credit Purchase Flow

```
User              Stripe             Backend            Database
  │                 │                   │                  │
  │  Checkout       │                   │                  │
  ├────────────────►│                   │                  │
  │                 │  Webhook          │                  │
  │                 ├──────────────────►│                  │
  │                 │                   │  Add credits     │
  │                 │                   ├─────────────────►│
  │                 │                   │                  │
  │                 │                   │  Referral bonus? │
  │                 │                   ├──────┐          │
  │                 │                   │      │ +10% to  │
  │                 │                   │      │ referrer │
  │                 │                   │◄─────┘          │
  │                 │                   │                  │
  │  ◄── Balance ───┤                   │                  │
```

---

## Database Schema

**Engine:** PostgreSQL (via asyncpg)  
**ORM:** SQLAlchemy 2.0 (async mode)  
**Base:** `database.py` → `Base(AsyncAttrs, DeclarativeBase)`

### Entity-Relationship Overview

```
┌──────────────┐     ┌────────────────────┐     ┌──────────────────┐
│    users     │────<│ credit_transactions │     │  whale_wallets   │
│──────────────│     │────────────────────│     │──────────────────│
│ id (PK, UUID)│     │ id (PK, UUID)      │     │ id (PK, UUID)    │
│ email        │     │ user_id (FK)       │     │ address (UNIQUE)  │
│ username     │     │ tx_type (ENUM)     │     │ label            │
│ hashed_pwd   │     │ amount             │     │ total_volume_usd │
│ credit_bal   │     │ balance_after      │     │ total_pnl_usd    │
│ referral_code│     │ description        │     │ win_rate         │
│ referred_by  │     │ stripe_payment_id  │     │ roi_pct          │
│ polymarket_* │     │ metadata_json      │     │ num_trades       │
│ created_at   │     │ created_at         │     │ num_markets      │
│ updated_at   │     └────────────────────┘     │ is_active        │
└──────┬───────┘                                 │ last_activity_at │
       │                                         │ discovered_at    │
       │         ┌──────────────────┐             └────────┬─────────┘
       ├────────<│   predictions    │                      │
       │         │──────────────────│             ┌────────▼─────────┐
       │         │ id (PK, UUID)    │             │ whale_positions  │
       │         │ user_id (FK)     │             │──────────────────│
       │         │ market_id        │             │ id (PK, UUID)    │
       │         │ question         │             │ wallet_id (FK)   │
       │         │ status (ENUM)    │             │ market_id        │
       │         │ verdict          │             │ market_question  │
       │         │ confidence       │             │ token_id         │
       │         │ debate_log (JSON)│             │ side             │
       │         │ agent_votes(JSON)│             │ size             │
       │         │ whale_alignment  │             │ avg_price        │
       │         │ created_at       │             │ current_price    │
       │         │ completed_at     │             │ pnl_usd          │
       │         └──────────────────┘             │ is_open          │
       │                                         │ opened_at        │
       │         ┌──────────────────┐             │ closed_at        │
       ├────────<│     trades       │             └──────────────────┘
       │         │──────────────────│
       │         │ id (PK, UUID)    │
       │         │ user_id (FK)     │
       │         │ market_id        │             ┌──────────────────┐
       │         │ token_id         │             │  chat_messages   │
       │         │ side (ENUM)      │             │──────────────────│
       │         │ amount_usd       │             │ id (PK, UUID)    │
       │         │ price            │             │ user_id (FK)     │
       │         │ size             │             │ role (ENUM)      │
       │         │ status (ENUM)    │             │ content          │
       │         │ order_id         │             │ metadata_json    │
       │         │ fee_usd          │             │ created_at       │
       │         │ pnl_usd          │             └──────────────────┘
       │         │ is_copy_trade    │
       │         │ copy_source_wallet│            ┌──────────────────┐
       │         │ prediction_id(FK)│             │    referrals     │
       │         │ created_at       │             │──────────────────│
       │         │ updated_at       │             │ id (PK, UUID)    │
       │         └──────────────────┘             │ referrer_id (FK) │
       │                                         │ referee_id (FK)  │
       └────────────────────────────────────────<│ referral_code    │
                                                 │ status           │
                                                 │ total_earned_cr  │
                                                 │ created_at       │
                                                 └──────────────────┘
```

### Tables Detail

#### `users`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, default uuid4 | Unique user identifier |
| `email` | VARCHAR(320) | UNIQUE, NOT NULL, INDEX | User email address |
| `username` | VARCHAR(64) | UNIQUE, NOT NULL, INDEX | Display username |
| `hashed_password` | VARCHAR(128) | NOT NULL | bcrypt-hashed password |
| `is_active` | BOOLEAN | default True | Account active status |
| `is_admin` | BOOLEAN | default False | Admin flag |
| `credit_balance` | INTEGER | default 0, NOT NULL | Current credit balance |
| `referral_code` | VARCHAR(16) | UNIQUE, INDEX | User's referral code |
| `referred_by` | UUID | FK → users.id | Who referred this user |
| `polymarket_api_key` | VARCHAR(256) | nullable | Encrypted API key |
| `polymarket_api_secret` | VARCHAR(256) | nullable | Encrypted API secret |
| `polymarket_passphrase` | VARCHAR(256) | nullable | Encrypted passphrase |
| `created_at` | TIMESTAMPTZ | server_default now() | Registration timestamp |
| `updated_at` | TIMESTAMPTZ | server_default now(), onupdate | Last update |

#### `credit_transactions`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Transaction ID |
| `user_id` | UUID | FK → users.id, INDEX | Owning user |
| `tx_type` | ENUM | NOT NULL | purchase, prediction, trade_fee, win_fee, referral_bonus, admin_adjustment |
| `amount` | INTEGER | NOT NULL | Credit delta (+/-) |
| `balance_after` | INTEGER | NOT NULL | Balance after this transaction |
| `description` | VARCHAR(512) | nullable | Human-readable description |
| `stripe_payment_id` | VARCHAR(256) | nullable | Stripe PaymentIntent ID |
| `metadata_json` | JSONB | nullable | Additional metadata |
| `created_at` | TIMESTAMPTZ | server_default now() | Transaction timestamp |

**Indexes:** `ix_credit_tx_user_created` on (user_id, created_at)

#### `predictions`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Prediction ID |
| `user_id` | UUID | FK → users.id, INDEX | Requesting user |
| `market_id` | VARCHAR(256) | NOT NULL, INDEX | Polymarket market ID |
| `question` | TEXT | NOT NULL | Market question |
| `status` | ENUM | default PENDING | pending, debating, completed, failed |
| `verdict` | VARCHAR(8) | nullable | YES or NO |
| `confidence` | FLOAT | nullable | 0.0 – 1.0 confidence score |
| `debate_log` | JSONB | nullable | Full debate transcript |
| `agent_votes` | JSONB | nullable | Individual agent votes |
| `whale_alignment` | FLOAT | nullable | Whale consensus alignment |
| `created_at` | TIMESTAMPTZ | server_default now() | Request timestamp |
| `completed_at` | TIMESTAMPTZ | nullable | Completion timestamp |

#### `trades`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Trade ID |
| `user_id` | UUID | FK → users.id, INDEX | Trading user |
| `market_id` | VARCHAR(256) | NOT NULL, INDEX | Polymarket market ID |
| `token_id` | VARCHAR(256) | NOT NULL | CLOB token ID |
| `side` | ENUM | NOT NULL | buy or sell |
| `amount_usd` | FLOAT | NOT NULL | Trade amount in USD |
| `price` | FLOAT | NOT NULL | Execution price |
| `size` | FLOAT | NOT NULL | Position size |
| `status` | ENUM | default PENDING | pending, placed, filled, partially_filled, cancelled, failed |
| `order_id` | VARCHAR(256) | nullable | Polymarket order ID |
| `fee_usd` | FLOAT | default 0.0 | Platform fee charged |
| `pnl_usd` | FLOAT | nullable | Realized P&L |
| `is_copy_trade` | BOOLEAN | default False | Whether this is a copy trade |
| `copy_source_wallet` | VARCHAR(64) | nullable | Source whale address |
| `prediction_id` | UUID | FK → predictions.id | Linked prediction |
| `created_at` | TIMESTAMPTZ | server_default now() | Order timestamp |
| `updated_at` | TIMESTAMPTZ | onupdate | Last status change |

**Indexes:** `ix_trade_user_created` on (user_id, created_at)

#### `whale_wallets`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Wallet record ID |
| `address` | VARCHAR(64) | UNIQUE, NOT NULL, INDEX | Polygon wallet address |
| `label` | VARCHAR(128) | nullable | Human-readable alias |
| `total_volume_usd` | FLOAT | default 0.0 | Lifetime trading volume |
| `total_pnl_usd` | FLOAT | default 0.0 | Lifetime profit/loss |
| `win_rate` | FLOAT | default 0.0 | Win percentage (0–1) |
| `roi_pct` | FLOAT | default 0.0 | Return on investment % |
| `num_trades` | INTEGER | default 0 | Total trades executed |
| `num_markets` | INTEGER | default 0 | Unique markets traded |
| `is_active` | BOOLEAN | default True | Currently tracked |
| `last_activity_at` | TIMESTAMPTZ | nullable | Last detected activity |
| `discovered_at` | TIMESTAMPTZ | server_default now() | When first discovered |
| `updated_at` | TIMESTAMPTZ | onupdate | Last data refresh |

#### `whale_positions`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Position record ID |
| `wallet_id` | UUID | FK → whale_wallets.id, INDEX | Parent whale wallet |
| `market_id` | VARCHAR(256) | NOT NULL, INDEX | Polymarket market ID |
| `market_question` | TEXT | nullable | Market question text |
| `token_id` | VARCHAR(256) | NOT NULL | CLOB token ID |
| `side` | VARCHAR(8) | NOT NULL | YES or NO |
| `size` | FLOAT | NOT NULL | Position size |
| `avg_price` | FLOAT | NOT NULL | Average entry price |
| `current_price` | FLOAT | nullable | Current market price |
| `pnl_usd` | FLOAT | nullable | Unrealized P&L |
| `is_open` | BOOLEAN | default True | Position still open |
| `opened_at` | TIMESTAMPTZ | server_default now() | Entry timestamp |
| `closed_at` | TIMESTAMPTZ | nullable | Exit timestamp |
| `updated_at` | TIMESTAMPTZ | onupdate | Last price update |

**Indexes:** `ix_whale_pos_wallet_market` on (wallet_id, market_id)

#### `chat_messages`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Message ID |
| `user_id` | UUID | FK → users.id, INDEX | Owning user |
| `role` | ENUM | NOT NULL | user, assistant, system |
| `content` | TEXT | NOT NULL | Message content |
| `metadata_json` | JSONB | nullable | Tokens used, context info |
| `created_at` | TIMESTAMPTZ | server_default now() | Message timestamp |

**Indexes:** `ix_chat_user_created` on (user_id, created_at)

#### `referrals`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Referral record ID |
| `referrer_id` | UUID | FK → users.id, INDEX | Referring user |
| `referee_id` | UUID | FK → users.id, UNIQUE | Referred user |
| `referral_code` | VARCHAR(16) | NOT NULL, INDEX | Code used |
| `status` | VARCHAR(16) | default "active" | active, expired, revoked |
| `total_earned_credits` | INTEGER | default 0 | Total bonus credits earned |
| `created_at` | TIMESTAMPTZ | server_default now() | When referral was made |

**Constraints:** `uq_referral_pair` UNIQUE on (referrer_id, referee_id)

---

## API Architecture

### Protocol

- **REST API:** JSON over HTTPS for all CRUD operations
- **WebSocket:** Real-time streaming for debates and chat
- **Authentication:** Bearer JWT tokens (HS256)

### Base Configuration

| Setting | Value |
|---------|-------|
| Base URL | `https://omen.market/api` |
| Content Type | `application/json` |
| Auth Header | `Authorization: Bearer <token>` |
| Access Token TTL | 30 minutes |
| Refresh Token TTL | 7 days |

### Router Registration

All routers are registered in `main.py` under the `/api` prefix:

```python
app.include_router(auth_router, prefix="/api")      # → /api/auth/*
app.include_router(credits_router, prefix="/api")    # → /api/credits/*
app.include_router(oracle_router, prefix="/api")     # → /api/oracle/*
app.include_router(whale_router, prefix="/api")      # → /api/whale/*
app.include_router(trading_router, prefix="/api")    # → /api/trading/*
app.include_router(chat_router, prefix="/api")       # → /api/chat/*
app.include_router(social_router, prefix="/api")     # → /api/social/*
```

See [API.md](./API.md) for complete endpoint documentation.

---

## Security Model

### Authentication

- **Password Hashing:** bcrypt via `passlib`
- **Token Signing:** JOSE/JWT with HS256 algorithm
- **Token Types:** Separate access (30m) and refresh (7d) tokens
- **Auth Dependency:** `get_current_user` extracts and validates tokens via `HTTPBearer`

### Authorization

- All data endpoints require valid Bearer token
- Users can only access their own data (user_id filtering on all queries)
- Admin flag on user model for future admin-only endpoints
- WebSocket endpoints accept token in initial message payload

### Data Protection

- Polymarket API credentials stored encrypted in database
- Stripe webhook signature verification in production
- SQL injection prevention via SQLAlchemy parameterized queries
- CORS restricted to configured origins
- Input validation via Pydantic v2 schemas on all endpoints

### Rate Limiting

- Credit-based rate limiting (1 credit per prediction)
- Redis-backed rate limiting for API endpoints (planned)
- Stripe webhook deduplication via payment_intent ID

---

## Scaling Strategy

### Horizontal Scaling

```
                    ┌─────────────┐
                    │ Load Balancer│
                    └──────┬──────┘
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │ Uvicorn  │ │ Uvicorn  │ │ Uvicorn  │
       │ Worker 1 │ │ Worker 2 │ │ Worker N │
       └────┬─────┘ └────┬─────┘ └────┬─────┘
            └─────────────┼─────────────┘
                    ┌─────▼──────┐
                    │ PostgreSQL │
                    │  (Primary) │
                    └─────┬──────┘
                          │
                    ┌─────▼──────┐
                    │ Read Replica│
                    └────────────┘
```

- **Application:** Multiple Uvicorn workers behind a load balancer
- **Database:** Connection pooling (pool_size=20, max_overflow=10) with read replicas
- **Cache:** Redis for session data, rate limits, and alert pub/sub
- **WebSockets:** Sticky sessions or Redis pub/sub for cross-worker communication

### Vertical Scaling

- Database: Increase pool_size and max_overflow via environment variables
- Workers: Increase Uvicorn worker count
- Memory: Increase container resource limits

### Future Scaling Considerations

- **Message Queue:** Celery/RQ for async prediction processing
- **Whale Scanning:** Background scheduler (APScheduler) for periodic scans
- **Search:** Elasticsearch for prediction/trade history search
- **CDN:** CloudFront/Cloudflare for static assets and brag card images

---

## Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Backend Framework** | FastAPI | Native async, auto-docs, Pydantic validation, high performance |
| **Database** | PostgreSQL + asyncpg | JSONB support for debate logs, ACID compliance, proven at scale |
| **ORM** | SQLAlchemy 2.0 (async) | Type-safe models, migration support, async session management |
| **Auth** | JWT (python-jose) + bcrypt | Stateless, scalable, industry standard |
| **LLM Provider** | OpenRouter → Gemini 2.0 Flash | Cost-effective, fast inference, good reasoning for debates |
| **Frontend** | Vue 3 + Vite | Composition API, fast HMR, excellent TypeScript support |
| **CSS** | Tailwind CSS v3 | Utility-first, consistent design, small bundle |
| **State Management** | Pinia | Vue 3 native, devtools support, composition API friendly |
| **Payments** | Stripe | Industry standard, webhook reliability, global coverage |
| **Cache/PubSub** | Redis | Fast, versatile, excellent WebSocket scaling support |
| **Containerization** | Docker + docker-compose | Reproducible deployments, easy local development |
| **Real-time** | FastAPI WebSockets | Native support, no extra dependencies |

---

## Directory Structure

```
omen/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Pydantic settings from env
│   ├── database.py          # Async engine, session factory, Base
│   ├── models.py            # All SQLAlchemy ORM models
│   ├── auth/
│   │   ├── router.py        # /api/auth/* endpoints
│   │   ├── schemas.py       # Pydantic request/response models
│   │   └── utils.py         # JWT, password hashing, get_current_user
│   ├── credits/
│   │   ├── router.py        # /api/credits/* endpoints
│   │   ├── schemas.py       # Credit Pydantic models
│   │   └── service.py       # Balance mutations, Stripe processing
│   ├── oracle/
│   │   ├── router.py        # /api/oracle/* endpoints + WS
│   │   ├── schemas.py       # Prediction Pydantic models
│   │   ├── swarm_engine.py  # Multi-agent coordination
│   │   ├── debate_simulator.py  # Debate execution + streaming
│   │   └── verdict.py       # Weighted consensus + whale alignment
│   ├── whale/
│   │   ├── router.py        # /api/whale/* endpoints
│   │   ├── schemas.py       # Whale Pydantic models
│   │   ├── tracker.py       # Position scanning + alerts
│   │   ├── discovery.py     # Whale wallet discovery
│   │   └── leaderboard.py   # Ranking logic
│   ├── trading/
│   │   ├── router.py        # /api/trading/* endpoints
│   │   ├── schemas.py       # Trade Pydantic models
│   │   ├── executor.py      # CLOB order placement
│   │   ├── copy_engine.py   # Copy-trading sessions
│   │   └── risk_manager.py  # Risk checks + limits
│   ├── chat/
│   │   ├── router.py        # /api/chat/* endpoints + WS
│   │   ├── schemas.py       # Chat Pydantic models
│   │   └── agent.py         # AI response generation
│   └── social/
│       ├── router.py        # /api/social/* endpoints
│       ├── schemas.py       # Social Pydantic models
│       ├── brag_cards.py    # SVG brag card generation
│       ├── referral.py      # Referral code management
│       └── twitter_bot.py   # X/Twitter integration
├── frontend/                # Vue 3 SPA
├── docs/                    # Documentation
├── scripts/                 # Database scripts
├── tests/                   # Test suite
├── docker-compose.yml       # Multi-service orchestration
├── Dockerfile               # Backend container
├── .env.example             # Environment template
└── README.md                # Project overview
```
