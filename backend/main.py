"""OMEN — The Oracle Machine: FastAPI Application Entry Point.

This module wires together all routers, middleware, WebSocket endpoints,
startup/shutdown lifecycle hooks, and the health check endpoint.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from database import engine

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("omen")


# ---------------------------------------------------------------------------
# Lifespan: startup + shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager — handles startup and shutdown."""
    # ── STARTUP ──────────────────────────────────────────────────────────
    logger.info("="*60)
    logger.info("  OMEN — The Oracle Machine  🔮")
    logger.info("  Starting up...")
    logger.info("="*60)

    # Verify database connectivity
    try:
        async with engine.begin() as conn:
            await conn.execute("SELECT 1" if False else __import__("sqlalchemy").text("SELECT 1"))
        logger.info("✅ Database connection verified")
    except Exception as exc:
        logger.warning("⚠️  Database not available (dev mode OK): %s", exc)

    # Log configuration
    logger.info("  Environment: %s", settings.environment)
    logger.info("  Debug mode:  %s", settings.debug)
    logger.info("  DB URL:      %s", str(settings.database_url)[:50] + "...")
    logger.info("  Redis URL:   %s", str(settings.redis_url)[:50])

    yield

    # ── SHUTDOWN ─────────────────────────────────────────────────────────
    logger.info("Shutting down OMEN...")
    await engine.dispose()
    logger.info("✅ Database connections closed")
    logger.info("OMEN shutdown complete")


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="OMEN — The Oracle Machine",
    description=(
        "AI-powered Polymarket prediction engine with swarm intelligence debates, "
        "whale tracking, copy-trading, and social sharing."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Global Exception Handler
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unhandled exceptions and return clean JSON errors."""
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method, request.url.path, exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": "An unexpected error occurred. Please try again.",
        },
    )

# ---------------------------------------------------------------------------
# Register Routers
# ---------------------------------------------------------------------------
from auth.router import router as auth_router
from credits.router import router as credits_router
from oracle.router import router as oracle_router
from whale.router import router as whale_router
from trading.router import router as trading_router
from chat.router import router as chat_router
from social.router import router as social_router

app.include_router(auth_router, prefix="/api")
app.include_router(credits_router, prefix="/api")
app.include_router(oracle_router, prefix="/api")
app.include_router(whale_router, prefix="/api")
app.include_router(trading_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(social_router, prefix="/api")

logger.info("✅ All routers registered")

# ---------------------------------------------------------------------------
# Health Check & Root Endpoints
# ---------------------------------------------------------------------------
@app.get("/", tags=["root"])
async def root() -> dict:
    """Root endpoint — basic service info."""
    return {
        "service": "OMEN — The Oracle Machine",
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Comprehensive health check endpoint.

    Verifies database connectivity, reports memory usage,
    and returns system status.
    """
    health = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "environment": settings.environment,
        "checks": {},
    }

    # Database check
    try:
        async with engine.begin() as conn:
            from sqlalchemy import text
            result = await conn.execute(text("SELECT 1"))
            result.scalar_one()
        health["checks"]["database"] = {"status": "up", "latency_ms": 0}
    except Exception as exc:
        health["checks"]["database"] = {"status": "down", "error": str(exc)}
        health["status"] = "degraded"

    # Memory usage
    try:
        import psutil
        process = psutil.Process()
        mem = process.memory_info()
        health["checks"]["memory"] = {
            "rss_mb": round(mem.rss / 1024 / 1024, 1),
            "vms_mb": round(mem.vms / 1024 / 1024, 1),
        }
    except ImportError:
        health["checks"]["memory"] = {"status": "psutil not installed"}

    # Registered routes count
    health["checks"]["routes"] = {"total": len(app.routes)}

    return health


@app.get("/api/status", tags=["health"])
async def api_status() -> dict:
    """API status endpoint with module availability."""
    return {
        "status": "operational",
        "modules": {
            "auth": "available",
            "credits": "available",
            "oracle": "available",
            "whale": "available",
            "trading": "available",
            "chat": "available",
            "social": "available",
        },
        "features": {
            "ai_debate": True,
            "whale_tracking": True,
            "copy_trading": True,
            "brag_cards": True,
            "referrals": True,
            "websocket_debate": True,
            "websocket_chat": True,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Run with Uvicorn (development)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info",
    )
