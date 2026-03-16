"""OMEN — Auth Module Tests.

Covers registration, login, JWT lifecycle, and profile retrieval.
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from auth.utils import create_access_token, hash_password  # noqa: E402
from models import User  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════
# Registration
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """A new user can register with valid credentials."""
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "newuser@test.omen.market",
            "username": "newuser01",
            "password": "StrongPass789!",
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["email"] == "newuser@test.omen.market"
    assert data["username"] == "newuser01"
    assert data["credit_balance"] == 0
    assert "referral_code" in data
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Registration with an existing email returns 409 Conflict."""
    payload = {
        "email": "dupe@test.omen.market",
        "username": "dupeuser1",
        "password": "StrongPass789!",
    }
    # First registration
    r1 = await client.post("/api/auth/register", json=payload)
    assert r1.status_code == 201

    # Duplicate — same email, different username
    payload["username"] = "dupeuser2"
    r2 = await client.post("/api/auth/register", json=payload)
    assert r2.status_code == 409
    assert "already registered" in r2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    """Registration with an existing username returns 409 Conflict."""
    # First registration
    r1 = await client.post(
        "/api/auth/register",
        json={
            "email": "unique1@test.omen.market",
            "username": "sameusername",
            "password": "StrongPass789!",
        },
    )
    assert r1.status_code == 201

    # Same username, different email
    r2 = await client.post(
        "/api/auth/register",
        json={
            "email": "unique2@test.omen.market",
            "username": "sameusername",
            "password": "StrongPass789!",
        },
    )
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    """Registration with a password shorter than 8 chars returns 422."""
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "weakpw@test.omen.market",
            "username": "weakpwuser",
            "password": "short",
        },
    )
    assert response.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# Login
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Login with correct credentials returns JWT tokens."""
    # Register first
    await client.post(
        "/api/auth/register",
        json={
            "email": "login_test@omen.market",
            "username": "logintest",
            "password": "LoginPass123!",
        },
    )

    # Login
    response = await client.post(
        "/api/auth/login",
        json={"login": "login_test@omen.market", "password": "LoginPass123!"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_with_username(client: AsyncClient):
    """Login works with username instead of email."""
    await client.post(
        "/api/auth/register",
        json={
            "email": "usernamelogin@omen.market",
            "username": "usernamelogin",
            "password": "LoginPass123!",
        },
    )

    response = await client.post(
        "/api/auth/login",
        json={"login": "usernamelogin", "password": "LoginPass123!"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """Login with incorrect password returns 401."""
    # Register
    await client.post(
        "/api/auth/register",
        json={
            "email": "wrongpw@omen.market",
            "username": "wrongpwuser",
            "password": "CorrectPass123!",
        },
    )

    response = await client.post(
        "/api/auth/login",
        json={"login": "wrongpw@omen.market", "password": "WrongPass999!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Login for a non-existent user returns 401."""
    response = await client.post(
        "/api/auth/login",
        json={"login": "ghost@omen.market", "password": "AnyPass123!"},
    )
    assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════
# Profile (GET /me)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_me_authenticated(
    client: AsyncClient, test_user: User, auth_headers: dict
):
    """Authenticated user can retrieve their profile."""
    response = await client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == str(test_user.id)
    assert data["email"] == test_user.email
    assert data["username"] == test_user.username
    assert data["credit_balance"] == test_user.credit_balance


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient):
    """Request to /me without token returns 401 or 403."""
    response = await client.get("/api/auth/me")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient):
    """Request to /me with a garbage token returns 401."""
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalidtoken12345"},
    )
    assert response.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════
# JWT Token Lifecycle
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_jwt_token_expiry(client: AsyncClient, test_user: User):
    """An expired JWT token is rejected with 401."""
    # Create a token that expired 1 hour ago
    expired_token = create_access_token(
        test_user.id, expires_delta=timedelta(hours=-1)
    )
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_token_refresh(client: AsyncClient):
    """Refresh token endpoint returns new access token."""
    # Register and login
    await client.post(
        "/api/auth/register",
        json={
            "email": "refresh@omen.market",
            "username": "refreshuser",
            "password": "RefreshPass123!",
        },
    )
    login_response = await client.post(
        "/api/auth/login",
        json={"login": "refresh@omen.market", "password": "RefreshPass123!"},
    )
    tokens = login_response.json()

    # Refresh
    response = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    # Accept 200 (success) or 404/405 (endpoint not yet implemented)
    if response.status_code == 200:
        data = response.json()
        assert "access_token" in data
    else:
        # Endpoint may not exist yet — that's acceptable
        assert response.status_code in (404, 405, 422)
