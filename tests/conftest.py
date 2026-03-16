"""OMEN — Shared Test Fixtures.

Provides:
- Async test database (SQLite in-memory)
- FastAPI TestClient with dependency overrides
- Authenticated test user + token helpers
- Database session fixture
"""

from __future__ import annotations

import asyncio
import secrets
import sys
import uuid
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from database import Base, get_session  # noqa: E402
from models import User  # noqa: E402
from auth.utils import create_access_token, hash_password  # noqa: E402

# ── Test Database (SQLite async in-memory) ────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

TestSessionFactory = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ── Event Loop ────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Database Setup/Teardown ───────────────────────────────────────────
@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """Create all tables once per test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture()
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean database session per test (with rollback)."""
    async with TestSessionFactory() as session:
        yield session
        await session.rollback()


# ── Override FastAPI dependency ───────────────────────────────────────
async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a test database session for FastAPI dependency injection."""
    async with TestSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── FastAPI App with overrides ────────────────────────────────────────
@pytest_asyncio.fixture()
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx AsyncClient connected to the test FastAPI app."""
    from main import app  # Import inside fixture to avoid early init

    app.dependency_overrides[get_session] = _override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        follow_redirects=True,
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Test User Helpers ─────────────────────────────────────────────────
TEST_USER_EMAIL = "test@omen.test"
TEST_USER_USERNAME = "testuser"
TEST_USER_PASSWORD = "TestPass123!"


@pytest_asyncio.fixture()
async def test_user(db_session: AsyncSession) -> User:
    """Create and return a test user with 100 credits."""
    user = User(
        id=uuid.uuid4(),
        email=f"test_{secrets.token_hex(4)}@omen.test",
        username=f"testuser_{secrets.token_hex(4)}",
        hashed_password=hash_password(TEST_USER_PASSWORD),
        is_active=True,
        credit_balance=100,
        referral_code=secrets.token_urlsafe(6)[:8].upper(),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture()
async def test_user_token(test_user: User) -> str:
    """Return a valid JWT access token for the test user."""
    return create_access_token(test_user.id)


@pytest_asyncio.fixture()
async def auth_headers(test_user_token: str) -> dict[str, str]:
    """Return Authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {test_user_token}"}


@pytest_asyncio.fixture()
async def second_user(db_session: AsyncSession) -> User:
    """Create a second test user for referral/multi-user tests."""
    user = User(
        id=uuid.uuid4(),
        email=f"second_{secrets.token_hex(4)}@omen.test",
        username=f"seconduser_{secrets.token_hex(4)}",
        hashed_password=hash_password("SecondPass456!"),
        is_active=True,
        credit_balance=50,
        referral_code=secrets.token_urlsafe(6)[:8].upper(),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
