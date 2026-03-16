#!/usr/bin/env python3
"""OMEN Live Deployment Launcher.
Patches database to SQLite, serves Vue frontend as static files.
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from contextlib import asynccontextmanager

# Add backend to path
BASE_DIR = Path(__file__).parent
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Override environment BEFORE importing anything
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{BASE_DIR}/data/omen.db"
os.environ["REDIS_URL"] = ""
os.environ["ENVIRONMENT"] = "production"
os.environ["DEBUG"] = "false"

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import hashlib
import secrets
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", stream=sys.stdout)
logger = logging.getLogger("omen")

# ── Database Setup (SQLite) ──────────────────────────────────────────────
import aiosqlite

DB_PATH = BASE_DIR / "data" / "omen.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

async def init_database():
    """Create SQLite tables."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                credits INTEGER DEFAULT 50,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                referral_code TEXT UNIQUE,
                referred_by TEXT
            );
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                question TEXT NOT NULL,
                verdict TEXT,
                confidence REAL,
                agents_data TEXT,
                whale_agreement TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                resolved INTEGER DEFAULT 0,
                correct INTEGER DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                prediction_id INTEGER,
                market_slug TEXT,
                side TEXT,
                amount_usd REAL,
                price REAL,
                shares REAL,
                trade_fee REAL,
                status TEXT DEFAULT "pending",
                pnl REAL DEFAULT 0,
                win_fee REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS whales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT UNIQUE NOT NULL,
                name TEXT,
                avatar_color TEXT DEFAULT "#7C3AED",
                win_rate REAL DEFAULT 0,
                total_trades INTEGER DEFAULT 0,
                profit_30d REAL DEFAULT 0,
                volume_total REAL DEFAULT 0,
                specialty TEXT DEFAULT "Mixed",
                followers INTEGER DEFAULT 0,
                is_featured INTEGER DEFAULT 0,
                last_active TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS whale_copies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                whale_id INTEGER,
                active INTEGER DEFAULT 1,
                max_trade_usd REAL DEFAULT 5.0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(whale_id) REFERENCES whales(id)
            );
            CREATE TABLE IF NOT EXISTS credit_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                type TEXT,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
        """)
        await db.commit()

        # Seed whales if empty
        cursor = await db.execute("SELECT COUNT(*) FROM whales")
        count = (await cursor.fetchone())[0]
        if count == 0:
            whales_data = [
                ("0xd91cfccfabd3a8b39f04bb6eca212d37c79b7bc8", "@0p0jogggg", "#7C3AED", 62.4, 17234, 168420, 1600000, "Sports", 847, 1),
                ("0x1a2b3c4d5e6f7890abcdef1234567890abcdef12", "@Sharky6999", "#3B82F6", 58.1, 8214, 94100, 890000, "Crypto", 523, 1),
                ("0x2b3c4d5e6f7890abcdef1234567890abcdef1234", "@CryptoKing", "#10B981", 71.3, 5412, 67300, 420000, "Politics", 412, 1),
                ("0x3c4d5e6f7890abcdef1234567890abcdef123456", "@DegenGambler", "#EF4444", 55.7, 12089, 43200, 1200000, "Sports", 289, 0),
                ("0x4d5e6f7890abcdef1234567890abcdef12345678", "@PolyMaxi", "#F59E0B", 64.2, 3812, 31400, 310000, "Mixed", 198, 0),
                ("0x5e6f7890abcdef1234567890abcdef1234567890", "@DataDriven", "#8B5CF6", 67.8, 2456, 28900, 245000, "Politics", 156, 0),
                ("0x6f7890abcdef1234567890abcdef12345678abcd", "@NBAWhale", "#F97316", 60.1, 9823, 82100, 950000, "Sports", 634, 1),
                ("0x7890abcdef1234567890abcdef12345678abcdef", "@ElectionEdge", "#EC4899", 73.5, 1892, 45600, 180000, "Politics", 321, 0),
            ]
            await db.executemany(
                "INSERT INTO whales (address, name, avatar_color, win_rate, total_trades, profit_30d, volume_total, specialty, followers, is_featured) VALUES (?,?,?,?,?,?,?,?,?,?)",
                whales_data
            )
            await db.commit()
            logger.info(f"Seeded {len(whales_data)} whales")
    logger.info("Database initialized")


# ── Password Hashing ─────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    return salt + ":" + hashlib.sha256((salt + password).encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    salt, hash_val = hashed.split(":", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == hash_val


# ── JWT (simple) ─────────────────────────────────────────────────────────
import base64, json as json_mod

JWT_SECRET = os.environ.get("JWT_SECRET", "omen-oracle-secret-key-2026")

def create_token(user_id: int, username: str) -> str:
    payload = {"user_id": user_id, "username": username, "exp": int(time.time()) + 86400}
    data = base64.urlsafe_b64encode(json_mod.dumps(payload).encode()).decode()
    sig = hashlib.sha256((data + JWT_SECRET).encode()).hexdigest()[:32]
    return f"{data}.{sig}"

def decode_token(token: str) -> Optional[dict]:
    try:
        data, sig = token.rsplit(".", 1)
        expected_sig = hashlib.sha256((data + JWT_SECRET).encode()).hexdigest()[:32]
        if sig != expected_sig:
            return None
        payload = json_mod.loads(base64.urlsafe_b64decode(data))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except:
        return None


# ── Oracle Engine (Simulated Swarm) ──────────────────────────────────────
import random

AGENTS = [
    {"name": "Atlas", "role": "Bull Analyst", "color": "#10B981", "icon": "A", "bias": 0.6},
    {"name": "Nemesis", "role": "Bear Analyst", "color": "#EF4444", "icon": "N", "bias": 0.4},
    {"name": "Quant", "role": "Statistician", "color": "#3B82F6", "icon": "Q", "bias": 0.5},
    {"name": "Maverick", "role": "Contrarian", "color": "#F59E0B", "icon": "M", "bias": 0.45},
    {"name": "Clio", "role": "Historian", "color": "#8B5CF6", "icon": "C", "bias": 0.55},
]

async def run_oracle(question: str) -> dict:
    """Simulate a swarm oracle prediction."""
    debates = []
    votes_yes = 0
    total_agents = 1200

    for agent in AGENTS:
        vote = random.random() < agent["bias"] + random.uniform(-0.15, 0.15)
        reasoning = generate_reasoning(agent["name"], agent["role"], question, vote)
        debates.append({
            "agent": agent["name"],
            "role": agent["role"],
            "color": agent["color"],
            "icon": agent["icon"],
            "vote": "YES" if vote else "NO",
            "reasoning": reasoning,
        })
        if vote:
            votes_yes += 1

    # Simulate full swarm vote
    swarm_yes = int(total_agents * (votes_yes / len(AGENTS)) + random.randint(-80, 80))
    swarm_yes = max(100, min(total_agents - 100, swarm_yes))
    confidence = round(max(swarm_yes, total_agents - swarm_yes) / total_agents * 100, 1)
    verdict = "YES" if swarm_yes > total_agents / 2 else "NO"

    # Whale agreement
    whale_agree = random.randint(2, 5)
    whale_total = 5

    return {
        "question": question,
        "verdict": verdict,
        "confidence": confidence,
        "debates": debates,
        "swarm_votes": {"yes": swarm_yes, "no": total_agents - swarm_yes, "total": total_agents},
        "whale_agreement": {"agree": whale_agree, "total": whale_total},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

def generate_reasoning(name, role, question, vote):
    bull_reasons = [
        f"Historical data strongly supports this outcome based on recent trends.",
        f"Market momentum and sentiment indicators are favorable.",
        f"Key fundamentals point toward a positive resolution here.",
        f"Similar situations in the past resolved positively 68% of the time.",
    ]
    bear_reasons = [
        f"Contrarian indicators suggest the market is overpricing this.",
        f"Key risk factors are being underweighted by the consensus.",
        f"Historical precedent shows reversals in similar setups.",
        f"The data doesn't support the current market pricing.",
    ]
    return random.choice(bull_reasons if vote else bear_reasons)


# ── FastAPI App ──────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("  OMEN — The Oracle Machine  🔮")
    logger.info("  LIVE DEPLOYMENT")
    logger.info("=" * 60)
    await init_database()
    yield
    logger.info("OMEN shutdown")

app = FastAPI(
    title="OMEN — The Oracle Machine",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ───────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    referral_code: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class PredictionRequest(BaseModel):
    question: str

class TradeRequest(BaseModel):
    prediction_id: int
    amount_usd: float
    side: str = "YES"


# ── Auth dependency ──────────────────────────────────────────────────────
async def get_current_user(request: Request) -> Optional[dict]:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return decode_token(auth[7:])
    return None


# ── API Routes ───────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "OMEN", "version": "1.0.0", "timestamp": datetime.now(timezone.utc).isoformat()}

# Auth
@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute("SELECT id FROM users WHERE username = ?", (req.username,))
        if await cursor.fetchone():
            return JSONResponse({"error": "Username taken"}, status_code=400)
        ref_code = secrets.token_hex(4)
        await db.execute(
            "INSERT INTO users (username, email, password_hash, credits, referral_code, referred_by) VALUES (?,?,?,?,?,?)",
            (req.username, req.email, hash_password(req.password), 50, ref_code, req.referral_code)
        )
        await db.commit()
        cursor = await db.execute("SELECT id FROM users WHERE username = ?", (req.username,))
        user = await cursor.fetchone()
        token = create_token(user[0], req.username)
        # Log credit transaction
        await db.execute("INSERT INTO credit_transactions (user_id, amount, type, description) VALUES (?,?,?,?)",
                        (user[0], 50, "signup_bonus", "Welcome bonus: 50 free credits"))
        await db.commit()
    return {"token": token, "username": req.username, "credits": 50, "referral_code": ref_code}

@app.post("/api/auth/login")
async def login(req: LoginRequest):
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute("SELECT id, password_hash, credits FROM users WHERE username = ?", (req.username,))
        row = await cursor.fetchone()
        if not row or not verify_password(req.password, row[1]):
            return JSONResponse({"error": "Invalid credentials"}, status_code=401)
        token = create_token(row[0], req.username)
    return {"token": token, "username": req.username, "credits": row[2]}

@app.get("/api/auth/me")
async def me(request: Request):
    user = await get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute("SELECT credits, referral_code, created_at FROM users WHERE id = ?", (user["user_id"],))
        row = await cursor.fetchone()
    return {"user_id": user["user_id"], "username": user["username"], "credits": row[0], "referral_code": row[1], "member_since": row[2]}

# Oracle
@app.post("/api/oracle/predict")
async def predict(req: PredictionRequest, request: Request):
    user = await get_current_user(request)
    user_id = user["user_id"] if user else None

    # Check credits
    if user_id:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cursor = await db.execute("SELECT credits FROM users WHERE id = ?", (user_id,))
            row = await cursor.fetchone()
            if row[0] < 1:
                return JSONResponse({"error": "Insufficient credits", "credits": row[0]}, status_code=402)
            # Deduct credit
            await db.execute("UPDATE users SET credits = credits - 1 WHERE id = ?", (user_id,))
            await db.execute("INSERT INTO credit_transactions (user_id, amount, type, description) VALUES (?,?,?,?)",
                           (user_id, -1, "prediction", f"Oracle prediction: {req.question[:50]}"))
            await db.commit()

    result = await run_oracle(req.question)

    # Save prediction
    if user_id:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            await db.execute(
                "INSERT INTO predictions (user_id, question, verdict, confidence, agents_data, whale_agreement) VALUES (?,?,?,?,?,?)",
                (user_id, req.question, result["verdict"], result["confidence"],
                 json_mod.dumps(result["debates"]), json_mod.dumps(result["whale_agreement"]))
            )
            await db.commit()
            cursor = await db.execute("SELECT credits FROM users WHERE id = ?", (user_id,))
            credits_left = (await cursor.fetchone())[0]
            result["credits_remaining"] = credits_left

    return result

@app.get("/api/oracle/free")
async def free_prediction():
    """Free daily oracle — no auth needed."""
    questions = [
        "Will Bitcoin be above $90,000 by end of March 2026?",
        "Will the Lakers make the NBA Playoffs?",
        "Will AI stocks outperform the S&P 500 this quarter?",
    ]
    question = random.choice(questions)
    result = await run_oracle(question)
    result["is_free"] = True
    return result

# Whales
@app.get("/api/whales")
async def list_whales():
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM whales ORDER BY profit_30d DESC")
        rows = await cursor.fetchall()
    return [{"id": r["id"], "address": r["address"], "name": r["name"], "avatar_color": r["avatar_color"],
             "win_rate": r["win_rate"], "total_trades": r["total_trades"], "profit_30d": r["profit_30d"],
             "volume_total": r["volume_total"], "specialty": r["specialty"], "followers": r["followers"],
             "is_featured": bool(r["is_featured"])} for r in rows]

@app.get("/api/whales/{whale_id}")
async def get_whale(whale_id: int):
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM whales WHERE id = ?", (whale_id,))
        r = await cursor.fetchone()
        if not r:
            return JSONResponse({"error": "Whale not found"}, status_code=404)
    return {"id": r["id"], "address": r["address"], "name": r["name"], "avatar_color": r["avatar_color"],
            "win_rate": r["win_rate"], "total_trades": r["total_trades"], "profit_30d": r["profit_30d"],
            "volume_total": r["volume_total"], "specialty": r["specialty"], "followers": r["followers"],
            "is_featured": bool(r["is_featured"])}

@app.post("/api/whales/{whale_id}/copy")
async def copy_whale(whale_id: int, request: Request):
    user = await get_current_user(request)
    if not user:
        return JSONResponse({"error": "Login required"}, status_code=401)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("INSERT OR REPLACE INTO whale_copies (user_id, whale_id, active) VALUES (?,?,1)",
                        (user["user_id"], whale_id))
        await db.execute("UPDATE whales SET followers = followers + 1 WHERE id = ?", (whale_id,))
        await db.commit()
    return {"status": "ok", "message": f"Now copying whale #{whale_id}"}

# Credits
@app.get("/api/credits/balance")
async def credit_balance(request: Request):
    user = await get_current_user(request)
    if not user:
        return JSONResponse({"error": "Login required"}, status_code=401)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute("SELECT credits FROM users WHERE id = ?", (user["user_id"],))
        row = await cursor.fetchone()
    return {"credits": row[0]}

@app.get("/api/credits/history")
async def credit_history(request: Request):
    user = await get_current_user(request)
    if not user:
        return JSONResponse({"error": "Login required"}, status_code=401)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM credit_transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
            (user["user_id"],)
        )
        rows = await cursor.fetchall()
    return [{"amount": r["amount"], "type": r["type"], "description": r["description"], "created_at": r["created_at"]} for r in rows]

@app.get("/api/credits/packages")
async def credit_packages():
    return [
        {"credits": 50, "price_usd": 5.00, "per_credit": 0.10, "popular": False},
        {"credits": 120, "price_usd": 10.00, "per_credit": 0.083, "popular": True},
        {"credits": 300, "price_usd": 20.00, "per_credit": 0.067, "popular": False},
        {"credits": 1000, "price_usd": 50.00, "per_credit": 0.050, "popular": False},
    ]

# Dashboard Stats
@app.get("/api/dashboard/stats")
async def dashboard_stats(request: Request):
    user = await get_current_user(request)
    if not user:
        return {
            "balance": 0, "win_rate": 71.2, "total_profit": 312.40,
            "active_copies": 3, "oracle_streak": 12, "predictions_today": 8,
            "correct_today": 6,
        }
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute("SELECT credits FROM users WHERE id = ?", (user["user_id"],))
        credits = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM predictions WHERE user_id = ?", (user["user_id"],))
        pred_count = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM whale_copies WHERE user_id = ? AND active = 1", (user["user_id"],))
        copies = (await cursor.fetchone())[0]
    return {
        "balance": credits * 0.10,
        "credits": credits,
        "win_rate": 71.2,
        "total_profit": 312.40,
        "active_copies": copies,
        "oracle_streak": 12,
        "predictions_total": pred_count,
    }

# Oracle streak / leaderboard
@app.get("/api/oracle/streak")
async def oracle_streak():
    return {"current_streak": 12, "best_streak": 18, "accuracy_30d": 71.2, "total_predictions": 847}

@app.get("/api/leaderboard")
async def leaderboard():
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM whales ORDER BY profit_30d DESC LIMIT 10")
        rows = await cursor.fetchall()
    return [{"rank": i+1, "name": r["name"], "win_rate": r["win_rate"], "profit_30d": r["profit_30d"],
             "followers": r["followers"], "specialty": r["specialty"]} for i, r in enumerate(rows)]

# WebSocket for live war room
@app.websocket("/ws/war-room")
async def war_room(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            question = json_mod.loads(data).get("question", "Will this happen?")
            result = await run_oracle(question)
            # Stream debates one by one
            for debate in result["debates"]:
                await websocket.send_json({"type": "debate", "data": debate})
                await asyncio.sleep(0.8)
            # Send verdict
            await websocket.send_json({"type": "verdict", "data": result})
    except WebSocketDisconnect:
        pass


# ── Serve Vue Frontend ───────────────────────────────────────────────────
FRONTEND_DIR = BASE_DIR / "frontend_dist"

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Try to serve the exact file first
        file_path = FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        # Fall back to index.html (SPA routing)
        return FileResponse(str(FRONTEND_DIR / "index.html"))
else:
    # No frontend build — serve a placeholder
    @app.get("/")
    async def index():
        return HTMLResponse(PLACEHOLDER_HTML)

PLACEHOLDER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>OMEN — The Oracle Machine</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg-primary: #0a0a0f;
  --bg-secondary: #0d1117;
  --bg-panel: #0f1218;
  --bg-terminal: #080b10;
  --border-glow: #00ff8840;
  --border-dim: #1a2332;
  --green: #00ff88;
  --green-dim: #00cc6a;
  --cyan: #00ffcc;
  --neon: #39ff14;
  --red: #ff3347;
  --red-dim: #cc2940;
  --yellow: #ffb800;
  --blue: #00aaff;
  --purple: #b44dff;
  --text-primary: #c9d1d9;
  --text-dim: #6a737d;
  --text-bright: #e6edf3;
  --glow-green: 0 0 10px #00ff8840, 0 0 20px #00ff8820;
  --glow-cyan: 0 0 10px #00ffcc40, 0 0 20px #00ffcc20;
  --glow-red: 0 0 10px #ff334740, 0 0 20px #ff334720;
  --font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

::selection { background: #00ff8830; color: #00ff88; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-primary); }
::-webkit-scrollbar-thumb { background: #1a2332; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #00ff8840; }

html { scroll-behavior: smooth; }

body {
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: var(--font-mono);
  min-height: 100vh;
  overflow-x: hidden;
  position: relative;
}

/* Matrix Rain Canvas */
#matrix-canvas {
  position: fixed;
  top: 0; left: 0;
  width: 100%; height: 100%;
  z-index: 0;
  opacity: 0.07;
  pointer-events: none;
}

/* Scanline overlay */
body::after {
  content: '';
  position: fixed;
  top: 0; left: 0;
  width: 100%; height: 100%;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0,255,136,0.015) 2px,
    rgba(0,255,136,0.015) 4px
  );
  pointer-events: none;
  z-index: 9999;
}

.main-container {
  position: relative;
  z-index: 1;
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 20px;
}

/* ══ HEADER ══ */
.header {
  text-align: center;
  padding: 60px 0 40px;
  position: relative;
}

.logo-text {
  font-size: 4.5rem;
  font-weight: 700;
  letter-spacing: 0.4em;
  color: var(--green);
  text-shadow: var(--glow-green), 0 0 60px #00ff8815;
  margin-bottom: 4px;
  animation: logoPulse 4s ease-in-out infinite;
}

@keyframes logoPulse {
  0%, 100% { text-shadow: var(--glow-green), 0 0 60px #00ff8815; }
  50% { text-shadow: 0 0 15px #00ff8860, 0 0 30px #00ff8830, 0 0 80px #00ff8820; }
}

.subtitle {
  font-size: 0.9rem;
  letter-spacing: 0.5em;
  color: var(--cyan);
  text-shadow: var(--glow-cyan);
  margin-bottom: 12px;
  font-weight: 300;
}

.tagline {
  color: var(--text-dim);
  font-size: 0.75rem;
  letter-spacing: 0.15em;
  margin-bottom: 30px;
  font-weight: 300;
}

/* Live stats bar */
.stats-bar {
  display: flex;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px 20px;
  background: var(--bg-terminal);
  border: 1px solid var(--border-dim);
  border-radius: 4px;
  max-width: 800px;
  margin: 0 auto;
  font-size: 0.7rem;
}

.stats-bar .stat-item {
  color: var(--text-dim);
  white-space: nowrap;
}

.stats-bar .stat-item .val {
  color: var(--green);
  font-weight: 500;
}

.stats-bar .stat-item .sep {
  color: #2a3544;
  margin: 0 4px;
}

/* ══ PANELS ══ */
.panel {
  background: var(--bg-panel);
  border: 1px solid var(--border-dim);
  border-radius: 6px;
  margin-bottom: 24px;
  overflow: hidden;
  transition: border-color 0.3s;
}

.panel:hover {
  border-color: var(--border-glow);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg-terminal);
  border-bottom: 1px solid var(--border-dim);
  font-size: 0.75rem;
  font-weight: 500;
  letter-spacing: 0.1em;
}

.panel-header .title {
  color: var(--cyan);
  text-shadow: var(--glow-cyan);
}

.panel-header .status {
  color: var(--green);
  font-size: 0.65rem;
}

.panel-header .status::before {
  content: '●';
  margin-right: 5px;
  animation: blink 2s infinite;
}

@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }

.panel-body {
  padding: 16px;
}

/* ══ GRID LAYOUT ══ */
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

@media (max-width: 900px) {
  .grid-2 { grid-template-columns: 1fr; }
  .logo-text { font-size: 2.8rem; }
}

@media (max-width: 600px) {
  .logo-text { font-size: 2rem; letter-spacing: 0.2em; }
  .stats-bar { font-size: 0.6rem; gap: 4px; }
  .panel-body { padding: 12px; }
}

/* ══ ORACLE TERMINAL ══ */
.terminal {
  background: var(--bg-terminal);
  border-radius: 4px;
  padding: 20px;
  font-size: 0.8rem;
  line-height: 1.7;
  min-height: 200px;
}

.terminal-line {
  margin-bottom: 2px;
}

.prompt-line {
  display: flex;
  align-items: center;
}

.prompt {
  color: var(--green);
  white-space: nowrap;
  margin-right: 6px;
  user-select: none;
}

.terminal-input {
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-bright);
  font-family: var(--font-mono);
  font-size: 0.8rem;
  flex: 1;
  caret-color: var(--green);
}

.cursor-blink {
  display: inline-block;
  width: 8px;
  height: 16px;
  background: var(--green);
  animation: cursorBlink 1s step-end infinite;
  vertical-align: middle;
  margin-left: 2px;
}

@keyframes cursorBlink { 0%,100%{opacity:1} 50%{opacity:0} }

.output-line { color: var(--text-dim); }
.output-line.green { color: var(--green); }
.output-line.red { color: var(--red); }
.output-line.cyan { color: var(--cyan); }
.output-line.yellow { color: var(--yellow); }
.output-line.blue { color: var(--blue); }
.output-line.purple { color: var(--purple); }
.output-line.bright { color: var(--text-bright); }

/* Loading bar */
.loading-bar-container {
  width: 100%;
  height: 4px;
  background: #1a2332;
  border-radius: 2px;
  margin: 8px 0;
  overflow: hidden;
}

.loading-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--green), var(--cyan));
  border-radius: 2px;
  width: 0%;
  transition: width 0.1s linear;
  box-shadow: 0 0 8px var(--green);
}

/* Verdict box */
.verdict-box {
  border: 1px solid var(--green);
  border-radius: 4px;
  padding: 16px;
  margin-top: 12px;
  text-align: center;
  background: #00ff8808;
  box-shadow: inset 0 0 30px #00ff8805, var(--glow-green);
}

.verdict-box.no {
  border-color: var(--red);
  background: #ff334708;
  box-shadow: inset 0 0 30px #ff334705, var(--glow-red);
}

.verdict-label {
  font-size: 0.65rem;
  letter-spacing: 0.3em;
  color: var(--text-dim);
  margin-bottom: 6px;
}

.verdict-text {
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--green);
  text-shadow: var(--glow-green);
}

.verdict-text.no { color: var(--red); text-shadow: var(--glow-red); }

.verdict-meta {
  font-size: 0.7rem;
  color: var(--text-dim);
  margin-top: 8px;
}

/* ══ WAR ROOM ══ */
.war-room-feed {
  background: var(--bg-terminal);
  border-radius: 4px;
  padding: 12px;
  height: 320px;
  overflow-y: auto;
  font-size: 0.7rem;
  line-height: 1.6;
}

.war-msg {
  padding: 3px 0;
  border-bottom: 1px solid #0d1520;
  animation: fadeInMsg 0.3s ease-out;
}

@keyframes fadeInMsg { from { opacity:0; transform:translateY(-5px); } to { opacity:1; transform:translateY(0); } }

.war-msg .ts { color: #3a4a5a; }
.war-msg .agent-name { font-weight: 500; }
.war-msg .vote-yes { color: var(--green); font-weight: 700; }
.war-msg .vote-no { color: var(--red); font-weight: 700; }

/* ══ SWARM MATRIX ══ */
.swarm-section { text-align: center; }

#swarm-canvas {
  width: 100%;
  max-width: 600px;
  height: 300px;
  border-radius: 4px;
  border: 1px solid var(--border-dim);
  background: var(--bg-terminal);
  display: block;
  margin: 0 auto;
}

.vote-counter {
  display: flex;
  justify-content: center;
  gap: 24px;
  margin-top: 12px;
  font-size: 0.75rem;
}

.vote-counter .vc-yes { color: var(--green); }
.vote-counter .vc-no { color: var(--red); }
.vote-counter .vc-abs { color: var(--yellow); }

.consensus-bar-wrap {
  width: 100%;
  max-width: 400px;
  height: 8px;
  background: var(--red);
  border-radius: 4px;
  margin: 12px auto 0;
  overflow: hidden;
  box-shadow: var(--glow-red);
}

.consensus-bar-fill {
  height: 100%;
  background: var(--green);
  border-radius: 4px;
  transition: width 0.5s;
  box-shadow: var(--glow-green);
}

/* ══ WHALE CARDS ══ */
.whale-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.whale-card {
  background: var(--bg-terminal);
  border: 1px solid var(--border-dim);
  border-radius: 4px;
  padding: 12px;
  font-size: 0.72rem;
  transition: border-color 0.3s, box-shadow 0.3s;
}

.whale-card:hover {
  border-color: var(--cyan);
  box-shadow: var(--glow-cyan);
}

.whale-card .wc-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px dashed #1a2332;
}

.whale-card .wc-name {
  color: var(--cyan);
  font-weight: 700;
  font-size: 0.8rem;
}

.whale-card .wc-badge {
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.05em;
}

.wc-badge.buy { background: #00ff8820; color: var(--green); border: 1px solid #00ff8840; }
.wc-badge.sell { background: #ff334720; color: var(--red); border: 1px solid #ff334740; }

.whale-card .wc-stats {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 6px;
  text-align: center;
}

.whale-card .wc-stat-label { color: var(--text-dim); font-size: 0.6rem; }
.whale-card .wc-stat-val { color: var(--text-bright); font-weight: 500; margin-top: 2px; }

/* ══ LEADERBOARD ══ */
.lb-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.72rem;
}

.lb-table th {
  text-align: left;
  padding: 8px 12px;
  color: var(--text-dim);
  font-weight: 400;
  font-size: 0.65rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  border-bottom: 1px solid var(--border-dim);
}

.lb-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #0d1520;
  color: var(--text-primary);
}

.lb-table tr:hover td { background: #0d151f; }

.lb-rank {
  color: var(--yellow);
  font-weight: 700;
  width: 40px;
}

.lb-name { color: var(--cyan); font-weight: 500; }
.lb-wr { color: var(--green); }
.lb-profit { color: var(--green); font-weight: 500; }
.lb-profit.neg { color: var(--red); }

/* ══ PRICING ══ */
.pricing-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.price-card {
  background: var(--bg-terminal);
  border: 1px solid var(--border-dim);
  border-radius: 4px;
  padding: 20px 16px;
  text-align: center;
  transition: border-color 0.3s, box-shadow 0.3s, transform 0.2s;
  cursor: pointer;
  position: relative;
}

.price-card:hover {
  border-color: var(--green);
  box-shadow: var(--glow-green);
  transform: translateY(-2px);
}

.price-card.popular {
  border-color: var(--cyan);
  box-shadow: var(--glow-cyan);
}

.price-card.popular::before {
  content: 'POPULAR';
  position: absolute;
  top: -10px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--cyan);
  color: var(--bg-primary);
  padding: 2px 12px;
  border-radius: 3px;
  font-size: 0.55rem;
  font-weight: 700;
  letter-spacing: 0.1em;
}

.price-credits {
  font-size: 2rem;
  font-weight: 700;
  color: var(--green);
  text-shadow: var(--glow-green);
}

.price-label {
  font-size: 0.65rem;
  color: var(--text-dim);
  letter-spacing: 0.1em;
  margin-bottom: 12px;
}

.price-amount {
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--text-bright);
  margin-bottom: 4px;
}

.price-per {
  font-size: 0.65rem;
  color: var(--text-dim);
}

/* ══ FOOTER ══ */
.footer {
  text-align: center;
  padding: 40px 20px;
  border-top: 1px solid var(--border-dim);
  margin-top: 20px;
}

.footer-brand {
  color: var(--text-dim);
  font-size: 0.7rem;
  letter-spacing: 0.15em;
  margin-bottom: 12px;
}

.footer-links {
  display: flex;
  justify-content: center;
  gap: 24px;
}

.footer-links a {
  color: var(--cyan);
  text-decoration: none;
  font-size: 0.7rem;
  transition: color 0.2s;
}

.footer-links a:hover { color: var(--green); text-shadow: var(--glow-green); }

/* ══ SECTION SPACING ══ */
.section {
  margin-bottom: 30px;
}

.section-title {
  font-size: 0.7rem;
  letter-spacing: 0.2em;
  color: var(--text-dim);
  margin-bottom: 16px;
  text-transform: uppercase;
}

/* ══ AGENT DEBATE CARDS (in oracle result) ══ */
.debate-card {
  background: var(--bg-terminal);
  border-left: 3px solid var(--green);
  padding: 10px 14px;
  margin: 6px 0;
  border-radius: 0 4px 4px 0;
  font-size: 0.75rem;
}

.debate-card.bear { border-left-color: var(--red); }
.debate-card .dc-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.debate-card .dc-agent { font-weight: 700; }
.debate-card .dc-role { color: var(--text-dim); font-size: 0.65rem; margin-left: 6px; }
.debate-card .dc-vote { font-weight: 700; }
.debate-card .dc-reasoning { color: var(--text-dim); font-size: 0.7rem; }

/* Loading spinner */
.spinner {
  display: inline-block;
  width: 14px; height: 14px;
  border: 2px solid var(--border-dim);
  border-top-color: var(--green);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
  margin-right: 6px;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* Glow button */
.glow-btn {
  background: transparent;
  border: 1px solid var(--green);
  color: var(--green);
  padding: 10px 24px;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.3s;
  letter-spacing: 0.1em;
  font-weight: 500;
}

.glow-btn:hover {
  background: var(--green);
  color: var(--bg-primary);
  box-shadow: var(--glow-green);
}

.glow-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Paygo note */
.paygo-note {
  text-align: center;
  color: var(--text-dim);
  font-size: 0.7rem;
  margin-top: 16px;
  letter-spacing: 0.05em;
}
</style>
</head>
<body>

<canvas id="matrix-canvas"></canvas>

<div class="main-container">

  <!-- ══ HEADER ══ -->
  <header class="header">
    <div class="logo-text">OMEN</div>
    <div class="subtitle">THE ORACLE MACHINE</div>
    <div class="tagline">Thousands of AI minds debate. One verdict. You profit.</div>
    <div class="stats-bar">
      <span class="stat-item"><span class="val" id="agents-count">1,247</span> agents online</span>
      <span class="stat-item"><span class="sep">|</span></span>
      <span class="stat-item"><span class="val" id="ops-count">5,000</span> ops/s</span>
      <span class="stat-item"><span class="sep">|</span></span>
      <span class="stat-item"><span class="val" id="latency-count">23</span>ms latency</span>
      <span class="stat-item"><span class="sep">|</span></span>
      <span class="stat-item"><span class="val" id="tokens-count">2.1M</span> tokens/cycle</span>
    </div>
  </header>

  <!-- ══ ORACLE TERMINAL ══ -->
  <section class="section">
    <div class="panel">
      <div class="panel-header">
        <span class="title">&#x1F52E; ORACLE TERMINAL</span>
        <span class="status">CONNECTED</span>
      </div>
      <div class="panel-body">
        <div class="terminal" id="oracle-terminal">
          <div class="terminal-line output-line green">OMEN Oracle v1.0 — Swarm Intelligence Engine</div>
          <div class="terminal-line output-line">1,200 agents loaded. Awaiting query...</div>
          <div class="terminal-line output-line">&nbsp;</div>
          <div id="oracle-output"></div>
          <div class="prompt-line">
            <span class="prompt">omen@oracle:~$&nbsp;</span>
            <input type="text" class="terminal-input" id="oracle-input" placeholder="Ask any prediction question..." autocomplete="off">
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- ══ WAR ROOM + SWARM MATRIX ══ -->
  <div class="grid-2 section">
    <!-- War Room -->
    <div class="panel">
      <div class="panel-header">
        <span class="title">&#x2694;&#xFE0F; WAR ROOM &mdash; LIVE AGENT FEED</span>
        <span class="status">STREAMING</span>
      </div>
      <div class="panel-body" style="padding:0">
        <div class="war-room-feed" id="war-feed"></div>
      </div>
    </div>

    <!-- Swarm Matrix -->
    <div class="panel">
      <div class="panel-header">
        <span class="title">&#x1F9EC; SWARM MATRIX &mdash; 1,200 AGENTS</span>
        <span class="status">LIVE</span>
      </div>
      <div class="panel-body swarm-section">
        <canvas id="swarm-canvas" width="600" height="300"></canvas>
        <div class="vote-counter">
          <span class="vc-yes">YES: <strong id="swarm-yes">687</strong> (<span id="swarm-yes-pct">57.3</span>%)</span>
          <span class="vc-no">NO: <strong id="swarm-no">453</strong> (<span id="swarm-no-pct">37.8</span>%)</span>
          <span class="vc-abs">ABSTAIN: <strong id="swarm-abs">60</strong> (<span id="swarm-abs-pct">5.0</span>%)</span>
        </div>
        <div class="consensus-bar-wrap">
          <div class="consensus-bar-fill" id="consensus-fill" style="width:57.3%"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- ══ WHALE TRACKER ══ -->
  <section class="section">
    <div class="panel">
      <div class="panel-header">
        <span class="title">&#x1F40B; WHALE INTELLIGENCE</span>
        <span class="status">TRACKING</span>
      </div>
      <div class="panel-body">
        <div class="whale-grid" id="whale-grid">
          <div style="color:var(--text-dim);font-size:0.7rem;">Loading whale data...</div>
        </div>
      </div>
    </div>
  </section>

  <!-- ══ LEADERBOARD ══ -->
  <section class="section">
    <div class="panel">
      <div class="panel-header">
        <span class="title">&#x1F3C6; LEADERBOARD</span>
        <span class="status">UPDATED</span>
      </div>
      <div class="panel-body" style="overflow-x:auto">
        <table class="lb-table" id="lb-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Name</th>
              <th>Specialty</th>
              <th>Win Rate</th>
              <th>30d Profit</th>
              <th>Followers</th>
            </tr>
          </thead>
          <tbody id="lb-body">
            <tr><td colspan="6" style="color:var(--text-dim);font-size:0.7rem;">Loading...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- ══ PRICING ══ -->
  <section class="section">
    <div class="panel">
      <div class="panel-header">
        <span class="title">&#x1F4B3; CREDIT PACKAGES</span>
        <span class="status">AVAILABLE</span>
      </div>
      <div class="panel-body">
        <div class="pricing-grid" id="pricing-grid">
          <div style="color:var(--text-dim);font-size:0.7rem;">Loading packages...</div>
        </div>
        <div class="paygo-note">No subscriptions. Pay as you go. 1 credit = 1 oracle query.</div>
      </div>
    </div>
  </section>

  <!-- ══ FOOTER ══ -->
  <footer class="footer">
    <div class="footer-brand">OMEN v1.0 &mdash; THE SWARM HAS SPOKEN</div>
    <div class="footer-links">
      <a href="/api/docs">API Docs</a>
      <a href="/api/whales">Whales API</a>
      <a href="/api/health">Health</a>
      <a href="#" onclick="document.getElementById('oracle-input').focus();return false;">Ask Oracle</a>
    </div>
  </footer>

</div>

<script>
/* ══════════════════════════════════════════════
   MATRIX RAIN
   ══════════════════════════════════════════════ */
(function() {
  const c = document.getElementById('matrix-canvas');
  const ctx = c.getContext('2d');
  let w, h, cols, drops;
  const chars = 'OMEN01ABCDEFアカサタナハマヤラワ';
  function resize() {
    w = c.width = window.innerWidth;
    h = c.height = window.innerHeight;
    const fs = 14;
    cols = Math.floor(w / fs);
    drops = new Array(cols).fill(1).map(() => Math.random() * h / fs | 0);
  }
  resize();
  window.addEventListener('resize', resize);
  function draw() {
    ctx.fillStyle = 'rgba(10,10,15,0.05)';
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = '#00ff88';
    ctx.font = '14px monospace';
    for (let i = 0; i < cols; i++) {
      const ch = chars[Math.random() * chars.length | 0];
      ctx.fillText(ch, i * 14, drops[i] * 14);
      if (drops[i] * 14 > h && Math.random() > 0.975) drops[i] = 0;
      drops[i]++;
    }
    requestAnimationFrame(draw);
  }
  draw();
})();

/* ══════════════════════════════════════════════
   LIVE STATS JITTER
   ══════════════════════════════════════════════ */
setInterval(() => {
  document.getElementById('agents-count').textContent = (1200 + Math.floor(Math.random()*100)).toLocaleString();
  document.getElementById('ops-count').textContent = (4800 + Math.floor(Math.random()*400)).toLocaleString();
  document.getElementById('latency-count').textContent = 18 + Math.floor(Math.random()*12);
  const t = [1.8,1.9,2.0,2.1,2.2,2.3][Math.floor(Math.random()*6)];
  document.getElementById('tokens-count').textContent = t.toFixed(1) + 'M';
}, 3000);

/* ══════════════════════════════════════════════
   ORACLE TERMINAL
   ══════════════════════════════════════════════ */
const oracleInput = document.getElementById('oracle-input');
const oracleOutput = document.getElementById('oracle-output');

function addLine(text, cls) {
  const div = document.createElement('div');
  div.className = 'terminal-line output-line' + (cls ? ' ' + cls : '');
  div.innerHTML = text;
  oracleOutput.appendChild(div);
  const term = document.getElementById('oracle-terminal');
  term.scrollTop = term.scrollHeight;
}

oracleInput.addEventListener('keydown', async function(e) {
  if (e.key !== 'Enter') return;
  const q = this.value.trim();
  if (!q) return;
  this.value = '';
  this.disabled = true;

  addLine('<span style="color:var(--green)">omen@oracle:~$</span> ' + escapeHtml(q), 'bright');
  addLine('&nbsp;');
  addLine('<span class="spinner"></span> SWARM DELIBERATING...', 'cyan');

  // Add loading bar
  const barWrap = document.createElement('div');
  barWrap.className = 'loading-bar-container';
  barWrap.innerHTML = '<div class="loading-bar" id="load-bar"></div>';
  oracleOutput.appendChild(barWrap);

  let pct = 0;
  const barEl = document.getElementById('load-bar');
  const barInt = setInterval(() => {
    pct = Math.min(pct + Math.random() * 15, 90);
    barEl.style.width = pct + '%';
  }, 200);

  try {
    const res = await fetch('/api/oracle/predict', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question: q})
    });
    const data = await res.json();
    clearInterval(barInt);
    barEl.style.width = '100%';

    if (data.error) {
      addLine('ERROR: ' + data.error, 'red');
      this.disabled = false;
      return;
    }

    setTimeout(() => {
      barWrap.remove();
      // Remove "SWARM DELIBERATING" line
      const lines = oracleOutput.querySelectorAll('.terminal-line');
      for (let l of lines) { if (l.innerHTML.includes('DELIBERATING')) l.remove(); }

      addLine('─── AGENT DEBATE LOG ───', 'cyan');
      if (data.debates) {
        data.debates.forEach(d => {
          const voteColor = d.vote === 'YES' ? 'var(--green)' : 'var(--red)';
          const voteIcon = d.vote === 'YES' ? '✅' : '❌';
          addLine(
            '<span style="color:' + d.color + ';font-weight:700">' + d.agent.toUpperCase() + '</span>' +
            ' <span style="color:var(--text-dim)">(' + d.role + ')</span> → ' +
            '<span style="color:var(--text-dim)">' + d.reasoning + '</span> ' +
            '<span style="color:' + voteColor + ';font-weight:700">VOTE: ' + d.vote + ' ' + voteIcon + '</span>'
          );
        });
      }

      addLine('&nbsp;');

      // Verdict
      const isYes = data.verdict === 'YES';
      const vCol = isYes ? 'var(--green)' : 'var(--red)';
      const boxDiv = document.createElement('div');
      boxDiv.className = 'verdict-box' + (isYes ? '' : ' no');
      boxDiv.innerHTML =
        '<div class="verdict-label">── ORACLE VERDICT ──</div>' +
        '<div class="verdict-text' + (isYes ? '' : ' no') + '">' + data.verdict + ' &mdash; ' + data.confidence + '% Confidence</div>' +
        '<div class="verdict-meta">' +
        '🐋 Whale Agreement: ' + (data.whale_agreement ? data.whale_agreement.agree + '/' + data.whale_agreement.total : 'N/A') +
        ' &nbsp;|&nbsp; Swarm: ' + (data.swarm_votes ? data.swarm_votes.yes + '/' + data.swarm_votes.total : 'N/A') +
        '</div>';
      oracleOutput.appendChild(boxDiv);
      addLine('&nbsp;');

      // Update swarm matrix
      if (data.swarm_votes) {
        updateSwarmVotes(data.swarm_votes.yes, data.swarm_votes.total - data.swarm_votes.yes - 60, 60);
      }

      this.disabled = false;
      this.focus();
    }, 500);

  } catch(err) {
    clearInterval(barInt);
    barWrap.remove();
    addLine('NETWORK ERROR: ' + err.message, 'red');
    this.disabled = false;
  }
});

function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

/* ══════════════════════════════════════════════
   WAR ROOM — SIMULATED LIVE FEED
   ══════════════════════════════════════════════ */
const warFeed = document.getElementById('war-feed');
const agentTypes = [
  { name: 'ATLAS', type: 'BULL', color: 'var(--green)', questions: [
    'Momentum indicators bullish. Historical win rate supports this.',
    'Public sentiment aligns with fundamentals. Strong probability.',
    'Key players healthy. Home advantage significant. Trend is clear.',
    'Market underpricing this outcome. Smart money accumulating.',
  ]},
  { name: 'NEMESIS', type: 'BEAR', color: 'var(--red)', questions: [
    'Contrarian signal detected. Market overpricing the favorite.',
    'Back-to-back schedule is brutal. Fatigue factor underweighted.',
    'Historical upset rate is 34% in these conditions. Caution advised.',
    'Injury reports not yet priced in. Expected correction incoming.',
  ]},
  { name: 'QUANT', type: 'STATS', color: 'var(--blue)', questions: [
    'Monte Carlo sim: 58.3% probability. EV +4.2%. Within error margin.',
    'Bayesian update: posterior probability shifted 3.2% after new data.',
    'Kelly criterion suggests 0.12 fractional bet size. Moderate edge.',
    'Regression model R-squared: 0.74. Significant predictive power.',
  ]},
  { name: 'MAVERICK', type: 'CONTRARIAN', color: 'var(--yellow)', questions: [
    '70%+ public on one side = fade signal. Taking the opposite.',
    'Sharp money diverging from public. Classic trap setup forming.',
    'Recency bias driving this line. True odds are different.',
    'Market has overcorrected. Value on the contrarian play.',
  ]},
  { name: 'CLIO', type: 'HISTORIAN', color: 'var(--purple)', questions: [
    'Similar matchups since 2019: 62% for the underdog in this spot.',
    'Historical pattern: teams in this situation cover 58% of the time.',
    'Last 5 years of data show clear seasonal trend favoring this outcome.',
    'Precedent analysis: 7 of 10 comparable situations resolved YES.',
  ]},
];

function genWarMsg() {
  const now = new Date();
  const ts = now.toTimeString().slice(0,8);
  const agent = agentTypes[Math.random() * agentTypes.length | 0];
  const id = 100 + Math.floor(Math.random() * 900);
  const msg = agent.questions[Math.random() * agent.questions.length | 0];
  const isYes = Math.random() > 0.45;
  const voteSpan = isYes
    ? '<span class="vote-yes">VOTE: YES ✅</span>'
    : '<span class="vote-no">VOTE: NO ❌</span>';

  const div = document.createElement('div');
  div.className = 'war-msg';
  div.innerHTML =
    '<span class="ts">[' + ts + ']</span> ' +
    '<span class="agent-name" style="color:' + agent.color + '">' + agent.name + ' #' + id + '</span> ' +
    '<span style="color:var(--text-dim)">(' + agent.type + ')</span> → ' +
    '<span style="color:var(--text-dim)">' + msg + '</span> ' + voteSpan;

  warFeed.appendChild(div);
  if (warFeed.children.length > 80) warFeed.removeChild(warFeed.firstChild);
  warFeed.scrollTop = warFeed.scrollHeight;
}

// Initial burst
for (let i = 0; i < 15; i++) genWarMsg();
setInterval(genWarMsg, 2200 + Math.random() * 1800);

/* ══════════════════════════════════════════════
   SWARM MATRIX CANVAS
   ══════════════════════════════════════════════ */
const swarmCanvas = document.getElementById('swarm-canvas');
const sCtx = swarmCanvas.getContext('2d');
const TOTAL_DOTS = 1200;
let yesCount = 687, noCount = 453, absCount = 60;
const dots = [];

function initDots() {
  dots.length = 0;
  const cw = swarmCanvas.width, ch = swarmCanvas.height;
  const cols = 48, rows = 25;
  const gapX = cw / (cols + 1), gapY = ch / (rows + 1);
  let idx = 0;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (idx >= TOTAL_DOTS) break;
      let type;
      if (idx < yesCount) type = 'yes';
      else if (idx < yesCount + noCount) type = 'no';
      else type = 'abs';
      dots.push({
        x: gapX * (c + 1),
        y: gapY * (r + 1),
        type: type,
        phase: Math.random() * Math.PI * 2,
        speed: 0.5 + Math.random() * 1.5,
        baseR: 3
      });
      idx++;
    }
  }
  // Shuffle for visual variety
  for (let i = dots.length - 1; i > 0; i--) {
    const j = Math.random() * (i + 1) | 0;
    [dots[i].type, dots[j].type] = [dots[j].type, dots[i].type];
  }
}

function updateSwarmVotes(y, n, a) {
  yesCount = y; noCount = n; absCount = a;
  const total = y + n + a;
  document.getElementById('swarm-yes').textContent = y;
  document.getElementById('swarm-no').textContent = n;
  document.getElementById('swarm-abs').textContent = a;
  document.getElementById('swarm-yes-pct').textContent = (y/total*100).toFixed(1);
  document.getElementById('swarm-no-pct').textContent = (n/total*100).toFixed(1);
  document.getElementById('swarm-abs-pct').textContent = (a/total*100).toFixed(1);
  document.getElementById('consensus-fill').style.width = (y/total*100).toFixed(1) + '%';
  // Reassign types
  let idx = 0;
  const shuffled = dots.slice().sort(() => Math.random() - 0.5);
  shuffled.forEach(d => {
    if (idx < y) d.type = 'yes';
    else if (idx < y + n) d.type = 'no';
    else d.type = 'abs';
    idx++;
  });
}

function drawSwarm(time) {
  const cw = swarmCanvas.width, ch = swarmCanvas.height;
  sCtx.clearRect(0, 0, cw, ch);

  dots.forEach(d => {
    const pulse = Math.sin(time * 0.001 * d.speed + d.phase) * 0.8;
    const r = d.baseR + pulse;
    let color;
    switch(d.type) {
      case 'yes': color = '#00ff88'; break;
      case 'no': color = '#ff3347'; break;
      default: color = '#ffb800'; break;
    }
    sCtx.beginPath();
    sCtx.arc(d.x, d.y, Math.max(1, r), 0, Math.PI * 2);
    sCtx.fillStyle = color;
    sCtx.globalAlpha = 0.6 + pulse * 0.15;
    sCtx.fill();
    // Glow
    sCtx.beginPath();
    sCtx.arc(d.x, d.y, r * 2, 0, Math.PI * 2);
    sCtx.fillStyle = color;
    sCtx.globalAlpha = 0.08;
    sCtx.fill();
    sCtx.globalAlpha = 1;
  });

  requestAnimationFrame(drawSwarm);
}

initDots();
requestAnimationFrame(drawSwarm);

// Periodically shift votes slightly for live feel
setInterval(() => {
  const dy = Math.floor(Math.random() * 7) - 3;
  const newYes = Math.max(400, Math.min(800, yesCount + dy));
  const newAbs = 50 + Math.floor(Math.random() * 20);
  const newNo = TOTAL_DOTS - newYes - newAbs;
  updateSwarmVotes(newYes, newNo, newAbs);
}, 4000);

/* ══════════════════════════════════════════════
   WHALE TRACKER
   ══════════════════════════════════════════════ */
fetch('/api/whales').then(r => r.json()).then(whales => {
  const grid = document.getElementById('whale-grid');
  grid.innerHTML = '';
  whales.forEach(w => {
    const isBuy = w.profit_30d > 30000;
    const card = document.createElement('div');
    card.className = 'whale-card';
    card.innerHTML =
      '<div class="wc-top">' +
        '<span class="wc-name">' + escapeHtml(w.name) + '</span>' +
        '<span class="wc-badge ' + (isBuy ? 'buy' : 'sell') + '">' + (isBuy ? '🟢 BUY' : '🔴 SELL') + '</span>' +
      '</div>' +
      '<div class="wc-stats">' +
        '<div><div class="wc-stat-label">WIN RATE</div><div class="wc-stat-val" style="color:var(--green)">' + w.win_rate.toFixed(1) + '%</div></div>' +
        '<div><div class="wc-stat-label">30D PnL</div><div class="wc-stat-val" style="color:' + (w.profit_30d >= 0 ? 'var(--green)' : 'var(--red)') + '">$' + (w.profit_30d / 1000).toFixed(0) + 'K</div></div>' +
        '<div><div class="wc-stat-label">FOLLOWERS</div><div class="wc-stat-val">' + w.followers + '</div></div>' +
      '</div>';
    grid.appendChild(card);
  });
}).catch(() => {
  document.getElementById('whale-grid').innerHTML = '<div style="color:var(--red);font-size:0.7rem;">Failed to load whale data</div>';
});

/* ══════════════════════════════════════════════
   LEADERBOARD
   ══════════════════════════════════════════════ */
fetch('/api/leaderboard').then(r => r.json()).then(lb => {
  const tbody = document.getElementById('lb-body');
  tbody.innerHTML = '';
  lb.forEach(entry => {
    const tr = document.createElement('tr');
    const profitStr = entry.profit_30d >= 0
      ? '+$' + (entry.profit_30d / 1000).toFixed(0) + 'K'
      : '-$' + (Math.abs(entry.profit_30d) / 1000).toFixed(0) + 'K';
    tr.innerHTML =
      '<td class="lb-rank">#' + entry.rank + '</td>' +
      '<td class="lb-name">' + escapeHtml(entry.name) + '</td>' +
      '<td style="color:var(--text-dim)">' + escapeHtml(entry.specialty) + '</td>' +
      '<td class="lb-wr">' + entry.win_rate.toFixed(1) + '%</td>' +
      '<td class="lb-profit' + (entry.profit_30d < 0 ? ' neg' : '') + '">' + profitStr + '</td>' +
      '<td style="color:var(--text-dim)">' + entry.followers + '</td>';
    tbody.appendChild(tr);
  });
}).catch(() => {
  document.getElementById('lb-body').innerHTML = '<tr><td colspan="6" style="color:var(--red);font-size:0.7rem;">Failed to load</td></tr>';
});

/* ══════════════════════════════════════════════
   PRICING
   ══════════════════════════════════════════════ */
fetch('/api/credits/packages').then(r => r.json()).then(pkgs => {
  const grid = document.getElementById('pricing-grid');
  grid.innerHTML = '';
  pkgs.forEach(p => {
    const card = document.createElement('div');
    card.className = 'price-card' + (p.popular ? ' popular' : '');
    card.innerHTML =
      '<div class="price-credits">' + p.credits + '</div>' +
      '<div class="price-label">CREDITS</div>' +
      '<div class="price-amount">$' + p.price_usd.toFixed(2) + '</div>' +
      '<div class="price-per">$' + p.per_credit.toFixed(3) + ' / credit</div>';
    grid.appendChild(card);
  });
}).catch(() => {
  document.getElementById('pricing-grid').innerHTML = '<div style="color:var(--red);font-size:0.7rem;">Failed to load packages</div>';
});

/* Focus oracle on load */
window.addEventListener('load', () => {
  setTimeout(() => document.getElementById('oracle-input').focus(), 500);
});
</script>
</body>
</html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8888, log_level="info")
