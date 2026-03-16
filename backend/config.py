"""OMEN Backend Configuration.

Loads all settings from environment variables with sensible defaults
for local development. Production deployments MUST set these via env.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    x_bearer_token: str = ""
    llm_model: str = "google/gemini-2.0-flash-exp:free"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173", "https://omen.market"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ──────────────────────────────────────────────────────────────
    app_name: str = "OMEN — The Oracle Machine"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"  # development | staging | production
    secret_key: str = "change-me-in-production-to-a-real-secret"
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    # ── Database ─────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://omen:omen@localhost:5432/omen"
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_echo: bool = False

    # ── Redis ────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── JWT ──────────────────────────────────────────────────────────────
    jwt_secret: str = "super-secret-jwt-key-change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 7

    # ── Stripe ───────────────────────────────────────────────────────────
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""  # Price ID for $5 = 50 credits product

    # ── MiroFish / Oracle ────────────────────────────────────────────────
    mirofish_api_url: str = "http://localhost:5001"
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemini-2.0-flash-exp:free"

    # ── Polymarket ───────────────────────────────────────────────────────
    polymarket_api_url: str = "https://clob.polymarket.com"
    polymarket_ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    polygon_rpc_url: str = "https://polygon-rpc.com"
    polymarket_api_key: str = ""
    polymarket_api_secret: str = ""
    polymarket_passphrase: str = ""

    # ── Twitter / X ──────────────────────────────────────────────────────
    twitter_api_key: str = ""
    twitter_api_secret: str = ""
    twitter_access_token: str = ""
    twitter_access_secret: str = ""

    # ── Credit Pricing ───────────────────────────────────────────────────
    credits_per_dollar: int = 10  # $5 = 50 credits  →  10 credits/$1
    prediction_cost_credits: int = 1
    trade_fee_pct: float = 0.025  # 2.5 %
    win_fee_pct: float = 0.05  # 5 %
    referral_bonus_pct: float = 0.10  # 10 % of referee purchases

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
