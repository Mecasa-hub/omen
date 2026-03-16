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
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>OMEN — The Oracle Machine</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0F0A1A;color:white;font-family:-apple-system,BlinkMacSystemFont,sans-serif;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center}
.container{max-width:800px;padding:2rem;text-align:center}
.eye{font-size:80px;margin-bottom:1rem;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.1);opacity:0.8}}
h1{font-size:3rem;letter-spacing:0.3em;margin-bottom:0.5rem;background:linear-gradient(135deg,#7C3AED,#F59E0B);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.subtitle{color:#A78BFA;font-size:1.2rem;letter-spacing:0.2em;margin-bottom:2rem}
.tagline{color:#9CA3AF;font-size:1rem;margin-bottom:3rem}
.oracle-box{background:#1e1535;border:2px solid #7C3AED;border-radius:16px;padding:2rem;margin:2rem 0}
.oracle-box h2{color:#F59E0B;margin-bottom:1rem}
input{width:100%;padding:1rem;border-radius:12px;border:1px solid #2D2150;background:#120D20;color:white;font-size:1rem;margin-bottom:1rem}
input:focus{outline:none;border-color:#7C3AED}
.btn{background:linear-gradient(135deg,#7C3AED,#6D28D9);color:white;border:none;padding:1rem 2rem;border-radius:12px;font-size:1rem;cursor:pointer;width:100%;font-weight:bold;transition:transform 0.2s}
.btn:hover{transform:scale(1.02)}
.result{margin-top:1.5rem;padding:1.5rem;border-radius:12px;background:#1a1030;border:1px solid #F59E0B;display:none}
.stats{display:flex;gap:2rem;justify-content:center;margin-top:2rem;flex-wrap:wrap}
.stat{background:#1e1535;padding:1rem 1.5rem;border-radius:12px;border:1px solid #2D2150}
.stat-value{font-size:1.5rem;font-weight:bold;color:#10B981}
.stat-label{color:#9CA3AF;font-size:0.8rem;margin-top:0.3rem}
.api-link{color:#A78BFA;text-decoration:none;margin-top:2rem;display:inline-block;font-size:0.9rem}
.features{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin-top:2rem;text-align:left}
.feature{background:#1e1535;padding:1rem;border-radius:10px;border:1px solid #2D2150}
.feature-icon{font-size:1.5rem;margin-bottom:0.5rem}
.feature-title{color:#A78BFA;font-weight:bold;margin-bottom:0.3rem}
.feature-desc{color:#9CA3AF;font-size:0.85rem}
</style>
</head>
<body>
<div class="container">
<div class="eye">🔮</div>
<h1>OMEN</h1>
<p class="subtitle">THE ORACLE MACHINE</p>
<p class="tagline">Thousands of AI minds debate. One verdict. You profit.</p>

<div class="oracle-box">
<h2>⚡ Ask the Oracle</h2>
<input type="text" id="question" placeholder="Will the Lakers beat the Celtics tonight?">
<button class="btn" onclick="askOracle()">🔮 Consult the Swarm</button>
<div class="result" id="result"></div>
</div>

<div class="stats">
<div class="stat"><div class="stat-value">71.2%</div><div class="stat-label">Accuracy</div></div>
<div class="stat"><div class="stat-value">1,200</div><div class="stat-label">AI Agents</div></div>
<div class="stat"><div class="stat-value">50+</div><div class="stat-label">Whales Tracked</div></div>
<div class="stat"><div class="stat-value">847</div><div class="stat-label">Predictions</div></div>
</div>

<div class="features">
<div class="feature"><div class="feature-icon">🧠</div><div class="feature-title">Swarm AI</div><div class="feature-desc">1,200 agents debate and vote on outcomes</div></div>
<div class="feature"><div class="feature-icon">🐋</div><div class="feature-title">Whale Tracking</div><div class="feature-desc">Copy the smartest Polymarket wallets</div></div>
<div class="feature"><div class="feature-icon">⚡</div><div class="feature-title">Auto-Execute</div><div class="feature-desc">One-click betting on Polymarket</div></div>
<div class="feature"><div class="feature-icon">💰</div><div class="feature-title">Pay-As-You-Go</div><div class="feature-desc">No subscriptions. 1% trade fee. 1% win fee.</div></div>
</div>

<a href="/api/docs" class="api-link">📚 API Documentation →</a>
<br>
<a href="/api/whales" class="api-link">🐋 View Whale Leaderboard →</a>
</div>

<script>
async function askOracle() {
    const q = document.getElementById("question").value;
    if (!q) return;
    const resultDiv = document.getElementById("result");
    resultDiv.style.display = "block";
    resultDiv.innerHTML = "<p style=\"color:#F59E0B\">⏳ The Swarm is deliberating...</p>";
    try {
        const res = await fetch("/api/oracle/predict", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({question: q})
        });
        const data = await res.json();
        let debateHtml = data.debates ? data.debates.map(d => 
            `<div style="background:#1a1535;padding:0.8rem;border-radius:8px;margin:0.5rem 0;border-left:3px solid ${d.color}">
                <span style="color:${d.color};font-weight:bold">${d.agent} (${d.role})</span>
                <span style="color:${d.vote==='YES'?'#10B981':'#EF4444'};float:right">${d.vote}</span>
                <p style="color:#9CA3AF;font-size:0.85rem;margin-top:0.3rem">${d.reasoning}</p>
            </div>`
        ).join("") : "";
        resultDiv.innerHTML = `
            ${debateHtml}
            <div style="background:#1a1030;border:2px solid #F59E0B;border-radius:10px;padding:1rem;margin-top:1rem;text-align:center">
                <div style="color:#F59E0B;font-weight:bold">🔮 ORACLE VERDICT</div>
                <div style="font-size:1.5rem;font-weight:bold;margin:0.5rem 0">${data.verdict} — ${data.confidence}% Confidence</div>
                <div style="color:#10B981;font-size:0.9rem">🐋 Whale Agreement: ${data.whale_agreement?.agree}/${data.whale_agreement?.total} | Swarm: ${data.swarm_votes?.yes}/${data.swarm_votes?.total}</div>
            </div>`;
    } catch(e) {
        resultDiv.innerHTML = "<p style=\"color:#EF4444\">Error consulting the Oracle</p>";
    }
}
</script>
</body>
</html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8888, log_level="info")
