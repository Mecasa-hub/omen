#!/usr/bin/env python3
"""OMEN Whale Alert X Bot.

Monitors tracked whales for new trades and auto-tweets alerts.
Designed for viral growth — each tweet is a free ad for OMEN.

Usage:
    python x_whale_bot.py                # Run once (tweet latest whale moves)
    python x_whale_bot.py --daemon       # Run continuously

Requires:
    OMEN_X_BEARER_TOKEN env var or .env file
"""

import asyncio
import json
import logging
import os
import sys
import time
import hashlib
import hmac
import aiosqlite
import httpx
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "omen.db"
STATE_FILE = BASE_DIR / "data" / "xbot_state.json"
LOG_FILE = "/tmp/omen_xbot.log"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE),
    ]
)
logger = logging.getLogger("omen_xbot")

# Polymarket API
GAMMA_API = "https://gamma-api.polymarket.com"
ACTIVITY_API = f"{GAMMA_API}/activity"

# Public OMEN URL (update with your actual domain)
OMEN_URL = os.environ.get("OMEN_URL", "https://inch-forbes-zone-tag.trycloudflare.com")


class WhaleAlertBot:
    """Auto-tweets whale trading alerts for viral growth."""

    def __init__(self):
        self.client: httpx.AsyncClient = None
        self.state = self._load_state()
        self.tweet_count = 0

        # X/Twitter API credentials
        self.api_key = os.environ.get("OMEN_X_API_KEY", "")
        self.api_secret = os.environ.get("OMEN_X_API_SECRET", "")
        self.access_token = os.environ.get("OMEN_X_ACCESS_TOKEN", "")
        self.access_secret = os.environ.get("OMEN_X_ACCESS_SECRET", "")

    def _load_state(self) -> dict:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
        return {"seen_activities": [], "last_scan": None, "tweets_today": 0, "tweet_history": []}

    def _save_state(self):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(self.state, indent=2))

    async def start(self):
        self.client = httpx.AsyncClient(timeout=30, headers={"User-Agent": "OMEN-XBot/1.0"}, follow_redirects=True)
        logger.info("🐦 OMEN Whale Alert X Bot started")
        logger.info(f"  OMEN URL: {OMEN_URL}")
        logger.info(f"  X API: {'Configured' if self.api_key else 'NOT configured (dry run)'}")

    async def stop(self):
        if self.client:
            await self.client.aclose()
        self._save_state()

    async def get_tracked_whales(self) -> list:
        """Get all tracked whales from OMEN database."""
        async with aiosqlite.connect(str(DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM whales ORDER BY profit_30d DESC")
            return [dict(r) for r in await cursor.fetchall()]

    async def fetch_whale_activity(self, address: str, limit: int = 10) -> list:
        """Fetch recent activity for a specific whale."""
        try:
            resp = await self.client.get(ACTIVITY_API, params={"address": address, "limit": limit})
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.debug(f"Activity fetch error for {address}: {e}")
        return []

    def format_tweet(self, whale: dict, activity: dict) -> str:
        """Format a viral whale alert tweet."""
        action = activity.get("type", "trade").upper()
        title = activity.get("title", "Unknown Market")[:60]
        amount = float(activity.get("usdcSize", 0) or activity.get("amount", 0) or 0)
        side = activity.get("side", "")

        # Emojis based on action
        if action in ("BUY", "TRADE"):
            emoji = "📈"
            action_text = "BOUGHT"
        else:
            emoji = "📉"
            action_text = "SOLD"

        # Star rating based on whale performance
        stars = "⭐" * min(5, int(whale.get("win_rate", 50) / 12))

        tweet = (
            f"🐋 WHALE ALERT {emoji}
"
            f"
"
            f"{whale.get('name', 'Unknown')} just {action_text} ${amount:,.0f} on:
"
            f"📊 {title}
"
        )

        if side:
            tweet += f"Side: {side.upper()}
"

        tweet += (
            f"
"
            f"Whale Stats:
"
            f"{stars} Win Rate: {whale.get('win_rate', 0)}%
"
            f"📈 30d Profit: ${whale.get('profit_30d', 0):,.0f}
"
            f"🔄 Total Trades: {whale.get('total_trades', 0):,}
"
            f"
"
            f"Copy this whale 👉 {OMEN_URL}
"
            f"
"
            f"#Polymarket #CopyTrading #OMEN"
        )

        # Ensure tweet is within character limit
        if len(tweet) > 280:
            tweet = tweet[:277] + "..."

        return tweet

    def format_oracle_tweet(self, prediction: dict) -> str:
        """Format an Oracle verdict tweet."""
        tweet = (
            f"🔮 ORACLE VERDICT
"
            f"
"
            f"Q: {prediction.get('question', '')[:80]}
"
            f"
"
            f"{'✅ YES' if prediction.get('verdict') == 'YES' else '❌ NO'} — "
            f"{prediction.get('confidence', 0)}% Confidence
"
            f"
"
            f"🧠 Swarm Vote: {prediction.get('swarm_votes', {}).get('yes', 0)}/{prediction.get('swarm_votes', {}).get('total', 1200)}
"
            f"🐋 Whale Agreement: {prediction.get('whale_agreement', {}).get('agree', 0)}/{prediction.get('whale_agreement', {}).get('total', 5)}
"
            f"
"
            f"Ask the Oracle 👉 {OMEN_URL}
"
            f"
"
            f"#Polymarket #AI #Predictions"
        )
        if len(tweet) > 280:
            tweet = tweet[:277] + "..."
        return tweet

    async def post_tweet(self, text: str) -> bool:
        """Post a tweet to X/Twitter."""
        if not self.api_key:
            logger.info(f"🐦 [DRY RUN] Would tweet:
{text}
{'='*50}")
            self.state["tweet_history"].append({
                "text": text,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "dry_run": True
            })
            self._save_state()
            return True

        try:
            # OAuth 1.0a signing
            url = "https://api.twitter.com/2/tweets"
            nonce = hashlib.md5(str(time.time()).encode()).hexdigest()
            timestamp = str(int(time.time()))

            # Build OAuth signature (simplified)
            params = {
                "oauth_consumer_key": self.api_key,
                "oauth_nonce": nonce,
                "oauth_signature_method": "HMAC-SHA1",
                "oauth_timestamp": timestamp,
                "oauth_token": self.access_token,
                "oauth_version": "1.0",
            }

            # Create signature base string
            param_string = "&".join(f"{quote(k)}={quote(v)}" for k, v in sorted(params.items()))
            base_string = f"POST&{quote(url)}&{quote(param_string)}"
            signing_key = f"{quote(self.api_secret)}&{quote(self.access_secret)}"
            signature = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
            import base64
            oauth_signature = base64.b64encode(signature).decode()

            auth_header = (
                f'OAuth oauth_consumer_key="{self.api_key}", '
                f'oauth_nonce="{nonce}", '
                f'oauth_signature="{quote(oauth_signature)}", '
                f'oauth_signature_method="HMAC-SHA1", '
                f'oauth_timestamp="{timestamp}", '
                f'oauth_token="{self.access_token}", '
                f'oauth_version="1.0"'
            )

            resp = await self.client.post(
                url,
                json={"text": text},
                headers={"Authorization": auth_header, "Content-Type": "application/json"}
            )

            if resp.status_code in (200, 201):
                logger.info(f"✅ Tweet posted successfully!")
                self.state["tweets_today"] += 1
                self.state["tweet_history"].append({
                    "text": text,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "success": True
                })
                self._save_state()
                return True
            else:
                logger.error(f"Tweet failed: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Tweet error: {e}")
            return False

    async def scan_and_tweet(self):
        """Scan for new whale activity and tweet alerts."""
        whales = await self.get_tracked_whales()
        logger.info(f"📡 Scanning {len(whales)} tracked whales...")

        new_alerts = []
        for whale in whales[:10]:  # Top 10 whales
            activities = await self.fetch_whale_activity(whale["address"])
            for act in activities:
                act_id = act.get("id") or act.get("transactionHash") or f"{whale['address']}_{act.get('createdAt')}"
                if act_id in self.state["seen_activities"]:
                    continue

                amount = float(act.get("usdcSize", 0) or act.get("amount", 0) or 0)
                if amount < 10:  # Skip tiny trades
                    continue

                new_alerts.append((whale, act, act_id))
            await asyncio.sleep(0.5)

        logger.info(f"  Found {len(new_alerts)} new whale trades")

        # Tweet top alerts (max 5 per scan to avoid spam)
        for whale, act, act_id in new_alerts[:5]:
            tweet = self.format_tweet(whale, act)
            success = await self.post_tweet(tweet)
            if success:
                self.state["seen_activities"].append(act_id)
                # Keep seen list manageable
                if len(self.state["seen_activities"]) > 1000:
                    self.state["seen_activities"] = self.state["seen_activities"][-500:]
                self.tweet_count += 1
            await asyncio.sleep(2)  # Space out tweets

        self.state["last_scan"] = datetime.now(timezone.utc).isoformat()
        self._save_state()
        return len(new_alerts)

    async def run_once(self):
        """Run a single scan and tweet cycle."""
        await self.start()
        try:
            count = await self.scan_and_tweet()
            logger.info(f"✅ Scan complete: {count} new alerts, {self.tweet_count} tweets sent")
        finally:
            await self.stop()

    async def run_daemon(self, interval_minutes: float = 5.0):
        """Run continuously, scanning every interval."""
        await self.start()
        logger.info(f"🔄 Daemon mode — scanning every {interval_minutes} minutes")
        try:
            while True:
                try:
                    await self.scan_and_tweet()
                except Exception as e:
                    logger.error(f"Scan error: {e}")
                await asyncio.sleep(interval_minutes * 60)
        finally:
            await self.stop()


if __name__ == "__main__":
    bot = WhaleAlertBot()
    if "--daemon" in sys.argv:
        asyncio.run(bot.run_daemon())
    else:
        asyncio.run(bot.run_once())
