# OMEN — The Oracle Machine: Deployment Guide

> **Version:** 1.0.0  
> **Last Updated:** 2026-03-16  
> **Target:** Production deployment on Linux (Ubuntu 22.04+ / Debian 12+)

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (Docker)](#quick-start-docker)
3. [Manual Deployment](#manual-deployment)
4. [Environment Configuration](#environment-configuration)
5. [Database Setup](#database-setup)
6. [SSL/TLS with Nginx](#ssltls-with-nginx)
7. [Cloudflare Setup](#cloudflare-setup)
8. [Monitoring & Logging](#monitoring--logging)
9. [Backup Strategy](#backup-strategy)
10. [Scaling](#scaling)
11. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 2 GB | 4+ GB |
| Disk | 20 GB SSD | 50+ GB SSD |
| OS | Ubuntu 22.04 / Debian 12 | Ubuntu 24.04 LTS |
| Python | 3.11+ | 3.12 |
| Node.js | 18+ | 20 LTS |
| PostgreSQL | 14+ | 16 |
| Redis | 7+ | 7.2+ |

### Required Software

```bash
# System packages
sudo apt update && sudo apt install -y \
  build-essential python3-pip python3-venv \
  postgresql postgresql-contrib redis-server \
  nginx certbot python3-certbot-nginx \
  curl git htop

# Docker (alternative to manual install)
curl -fsSL https://get.docker.com | sh
sudo apt install -y docker-compose-plugin
```

### Required Accounts & API Keys

| Service | Purpose | Required |
|---------|---------|----------|
| **OpenRouter** | LLM API for Oracle debates | ✅ |
| **Stripe** | Payment processing | ✅ (for production) |
| **Polymarket** | CLOB trading API | ✅ (for live trading) |
| **X/Twitter** | Social bot API v2 | ❌ (optional) |

---

## Quick Start (Docker)

The fastest way to deploy OMEN in production:

### 1. Clone and Configure

```bash
git clone https://github.com/your-org/omen.git
cd omen
cp .env.example .env
```

Edit `.env` with your production values (see [Environment Configuration](#environment-configuration)).

### 2. Build and Run

```bash
# Build and start all services
docker compose up -d --build

# Verify everything is running
docker compose ps

# Check logs
docker compose logs -f backend
```

### 3. Initialize Database

```bash
# Run migrations
docker compose exec backend python scripts/migrate_db.py

# (Optional) Seed whale data
docker compose exec backend python scripts/seed_whales.py

# (Optional) Generate demo data
docker compose exec backend python scripts/generate_demo.py
```

### 4. Verify

```bash
# Health check
curl http://localhost:8000/health

# API status
curl http://localhost:8000/api/status
```

### docker-compose.yml Reference

```yaml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    volumes:
      - ./backend:/app/backend
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: omen
      POSTGRES_PASSWORD: ${DB_PASSWORD:-omen_secret}
      POSTGRES_DB: omen
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U omen"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  pgdata:
  redisdata:
```

---

## Manual Deployment

### 1. Create Application User

```bash
sudo useradd -m -s /bin/bash omen
sudo su - omen
```

### 2. Clone Repository

```bash
git clone https://github.com/your-org/omen.git ~/omen
cd ~/omen
```

### 3. Python Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
```

### 4. PostgreSQL Setup

```bash
sudo -u postgres psql << SQL
CREATE USER omen WITH PASSWORD 'your_secure_password';
CREATE DATABASE omen OWNER omen;
GRANT ALL PRIVILEGES ON DATABASE omen TO omen;
\c omen
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
SQL
```

### 5. Redis Setup

```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server
redis-cli ping  # Should return PONG
```

### 6. Environment File

```bash
cp .env.example .env
nano .env  # Edit with production values
```

### 7. Database Migration

```bash
cd ~/omen/backend
python ../scripts/migrate_db.py
```

### 8. Frontend Build

```bash
cd ~/omen/frontend
npm install
npm run build  # Output to dist/
```

### 9. Systemd Service

Create `/etc/systemd/system/omen.service`:

```ini
[Unit]
Description=OMEN - The Oracle Machine Backend
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
Type=exec
User=omen
Group=omen
WorkingDirectory=/home/omen/omen/backend
EnvironmentFile=/home/omen/omen/.env
ExecStart=/home/omen/omen/venv/bin/uvicorn main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-level info \
  --access-log
Restart=always
RestartSec=5
StartLimitInterval=60
StartLimitBurst=5

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/home/omen/omen
ProtectHome=read-only
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable omen
sudo systemctl start omen
sudo systemctl status omen
```

---

## Environment Configuration

All settings are loaded from environment variables via Pydantic `BaseSettings`.

### Required Variables

```bash
# ── Application ──────────────────────────────────────────────
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=generate-a-64-char-random-string-here

# ── Database ─────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://omen:PASSWORD@localhost:5432/omen
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_ECHO=false

# ── Redis ────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── JWT ──────────────────────────────────────────────────────
JWT_SECRET=generate-another-64-char-random-string
JWT_ALGORITHM=HS256
JWT_ACCESS_EXPIRE_MINUTES=30
JWT_REFRESH_EXPIRE_DAYS=7

# ── Stripe ───────────────────────────────────────────────────
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...

# ── OpenRouter (LLM) ────────────────────────────────────────
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free

# ── Polymarket ───────────────────────────────────────────────
POLYMARKET_API_KEY=your-api-key
POLYMARKET_API_SECRET=your-api-secret
POLYMARKET_PASSPHRASE=your-passphrase
POLYMARKET_API_URL=https://clob.polymarket.com
POLYGON_RPC_URL=https://polygon-rpc.com

# ── Twitter/X (Optional) ────────────────────────────────────
TWITTER_API_KEY=
TWITTER_API_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_SECRET=

# ── CORS ─────────────────────────────────────────────────────
ALLOWED_ORIGINS=https://omen.market,https://www.omen.market
CORS_ORIGINS=["https://omen.market","https://www.omen.market"]
```

### Generate Secure Keys

```bash
# Generate SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# Generate JWT_SECRET
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## Database Setup

### Initial Migration

```bash
cd /home/omen/omen
source venv/bin/activate
python scripts/migrate_db.py
```

This creates all 8 tables idempotently:
- `users`
- `credit_transactions`
- `predictions`
- `trades`
- `whale_wallets`
- `whale_positions`
- `chat_messages`
- `referrals`

### Seed Data (Optional)

```bash
# Seed known whale wallets
python scripts/seed_whales.py

# Generate demo data for testing
python scripts/generate_demo.py
```

### Production Database Tuning

Add to `/etc/postgresql/16/main/postgresql.conf`:

```ini
# Connection settings
max_connections = 200

# Memory settings (adjust for available RAM)
shared_buffers = 1GB
effective_cache_size = 3GB
work_mem = 16MB
maintenance_work_mem = 256MB

# WAL settings
wal_buffers = 64MB
checkpoint_completion_target = 0.9

# Query planner
random_page_cost = 1.1  # SSD
effective_io_concurrency = 200

# Logging
log_min_duration_statement = 1000  # Log queries > 1s
log_checkpoints = on
log_connections = on
log_disconnections = on
```

---

## SSL/TLS with Nginx

### Nginx Configuration

Create `/etc/nginx/sites-available/omen`:

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name omen.market www.omen.market;
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name omen.market www.omen.market;

    # SSL certificates (managed by Certbot)
    ssl_certificate /etc/letsencrypt/live/omen.market/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/omen.market/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin";

    # Frontend (Vue SPA)
    location / {
        root /home/omen/omen/frontend/dist;
        try_files $uri $uri/ /index.html;

        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|svg|ico|woff2?)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts for AI predictions (can take 10-30s)
        proxy_read_timeout 60s;
        proxy_connect_timeout 10s;
    }

    # WebSocket proxy for debates
    location /api/oracle/ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }

    # WebSocket proxy for chat
    location /api/chat/ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }

    # FastAPI docs
    location /docs {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }

    location /redoc {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }

    # Health check (no auth needed)
    location /health {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

### Enable and Get Certificate

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/omen /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Get SSL certificate
sudo certbot --nginx -d omen.market -d www.omen.market

# Auto-renewal (certbot sets this up automatically)
sudo certbot renew --dry-run
```

---

## Cloudflare Setup

### DNS Configuration

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | omen.market | `<server-ip>` | ✅ Proxied |
| A | www | `<server-ip>` | ✅ Proxied |
| CNAME | api | omen.market | ✅ Proxied |

### Recommended Settings

**SSL/TLS:**
- Encryption mode: Full (strict)
- Always Use HTTPS: On
- Minimum TLS Version: 1.2

**Performance:**
- Auto Minify: JS, CSS, HTML
- Brotli: On
- Rocket Loader: Off (can break Vue SPA)

**Security:**
- WAF: On (Managed Rules)
- Bot Fight Mode: On
- Rate Limiting Rules:
  - `/api/auth/*`: 10 req/min per IP
  - `/api/oracle/*`: 20 req/min per IP
  - `/api/*`: 100 req/min per IP

**Caching:**
- Cache Level: Standard
- Browser Cache TTL: 1 year (for hashed assets)
- Page Rules:
  - `omen.market/api/*` → Cache Level: Bypass
  - `omen.market/health` → Cache Level: Bypass

### WebSocket Support

Cloudflare supports WebSockets on all paid plans. For the Free plan:
- WebSockets are supported by default
- Ensure "WebSockets" is enabled in Network settings

---

## Monitoring & Logging

### Application Logs

```bash
# View live logs
journalctl -u omen -f

# View last 100 lines
journalctl -u omen -n 100

# View logs since today
journalctl -u omen --since today
```

### Log Format

OMEN uses structured logging:

```
2026-03-16 12:00:00 | INFO     | omen                      | ✅ Database connection verified
2026-03-16 12:00:01 | INFO     | auth.router               | New user registered: trader (trader@example.com)
2026-03-16 12:00:05 | INFO     | oracle.router             | Prediction completed: id=abc market=0x123 verdict=YES confidence=74.0%
```

### Health Check Monitoring

Create `/etc/cron.d/omen-health`:

```cron
*/5 * * * * root curl -sf http://localhost:8000/health > /dev/null || systemctl restart omen
```

### Database Monitoring

```sql
-- Active connections
SELECT count(*) FROM pg_stat_activity WHERE datname = 'omen';

-- Slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
WHERE dbid = (SELECT oid FROM pg_database WHERE datname = 'omen')
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Table sizes
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
```

### Prometheus Metrics (Optional)

Add `prometheus-fastapi-instrumentator` for metrics:

```python
# In main.py
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)
```

Scrape at `http://localhost:8000/metrics`.

---

## Backup Strategy

### Database Backups

Create `/home/omen/scripts/backup_db.sh`:

```bash
#!/bin/bash
set -euo pipefail

BACKUP_DIR="/home/omen/backups/db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

# Full database dump
pg_dump -U omen -h localhost omen \
  --format=custom \
  --compress=9 \
  > "$BACKUP_DIR/omen_$TIMESTAMP.dump"

# Clean old backups
find "$BACKUP_DIR" -name "*.dump" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: omen_$TIMESTAMP.dump"
echo "Size: $(du -h $BACKUP_DIR/omen_$TIMESTAMP.dump | cut -f1)"
```

### Backup Schedule

```cron
# /etc/cron.d/omen-backup
# Daily at 3:00 AM UTC
0 3 * * * omen /home/omen/scripts/backup_db.sh >> /home/omen/logs/backup.log 2>&1
```

### Restore from Backup

```bash
# Restore full database
pg_restore -U omen -h localhost -d omen --clean --if-exists \
  /home/omen/backups/db/omen_20260316_030000.dump
```

### Off-site Backup

```bash
# Sync to S3 (or compatible)
aws s3 sync /home/omen/backups/db/ s3://omen-backups/db/ \
  --storage-class STANDARD_IA
```

---

## Scaling

### Horizontal Scaling (Application)

```bash
# Increase Uvicorn workers (1 per CPU core)
uvicorn main:app --workers 8 --host 0.0.0.0 --port 8000

# Or use Gunicorn with Uvicorn workers
gunicorn main:app -w 8 -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### Vertical Scaling (Database)

```bash
# Increase connection pool
DB_POOL_SIZE=50
DB_MAX_OVERFLOW=25
```

### Multi-Server Deployment

For traffic beyond a single server:

1. **Load Balancer:** Nginx/HAProxy distributes traffic
2. **Sticky Sessions:** Required for WebSocket connections
3. **Shared State:** Redis for session/rate-limit data
4. **Database:** Primary + read replicas for query scaling
5. **CDN:** Cloudflare/CloudFront for static assets

---

## Troubleshooting

### Common Issues

#### Backend won't start

```bash
# Check logs
journalctl -u omen -n 50 --no-pager

# Test database connection
python3 -c "
import asyncio, asyncpg
async def test():
    conn = await asyncpg.connect('postgresql://omen:PASSWORD@localhost/omen')
    print(await conn.fetchval('SELECT 1'))
    await conn.close()
asyncio.run(test())
"

# Test Redis connection
redis-cli ping
```

#### Database connection errors

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check connection limit
sudo -u postgres psql -c "SHOW max_connections;"
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity;"

# Check pg_hba.conf allows local connections
sudo cat /etc/postgresql/16/main/pg_hba.conf | grep omen
```

#### WebSocket connection fails

```bash
# Test WebSocket directly
python3 -c "
import asyncio, websockets
async def test():
    async with websockets.connect('ws://localhost:8000/api/chat/ws/chat') as ws:
        print('Connected!')
asyncio.run(test())
"

# Check Nginx WebSocket config
nginx -t
grep -n 'Upgrade\|websocket' /etc/nginx/sites-enabled/omen
```

#### High memory usage

```bash
# Check process memory
ps aux --sort=-%mem | head -5

# Check database pool
python3 -c "
from database import engine
print(f'Pool size: {engine.pool.size()}')
print(f'Checked in: {engine.pool.checkedin()}')
print(f'Checked out: {engine.pool.checkedout()}')
"
```

#### Prediction timeouts

```bash
# Check OpenRouter API
curl -s https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | jq '.data[0].id'

# Increase Nginx timeout
# proxy_read_timeout 120s;  (in nginx config)
```

### Emergency Procedures

```bash
# Restart all services
sudo systemctl restart omen postgresql redis-server nginx

# Kill stuck connections
sudo -u postgres psql -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'omen' AND state = 'idle in transaction'
AND query_start < NOW() - interval '5 minutes';
"

# Clear Redis cache
redis-cli FLUSHDB

# Emergency DB backup
pg_dump -U omen omen -Fc > /tmp/emergency_backup.dump
```
