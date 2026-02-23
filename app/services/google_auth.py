from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


def _get_fernet() -> Fernet:
    return Fernet(settings.token_encryption_key.encode())


def encrypt_token(token: str) -> str:
    return _get_fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    return _get_fernet().decrypt(encrypted.encode()).decode()


def get_auth_url(state: str | None = None) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(settings.google_scopes),
        "access_type": "offline",
        "prompt": "consent",
    }
    if state:
        params["state"] = state
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_AUTH_URL}?{query}"


async def exchange_code(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(refresh_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_user_email(access_token: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()["email"]


async def get_valid_token(user: User, db: AsyncSession) -> str:
    """Get a valid access token, refreshing if expired."""
    if not user.google_access_token or not user.google_refresh_token:
        raise ValueError("User has no Google tokens configured")

    access_token = decrypt_token(user.google_access_token)

    if user.token_expiry and user.token_expiry > datetime.now(timezone.utc):
        return access_token

    logger.info("Refreshing token for user %s", user.email)
    refresh_token = decrypt_token(user.google_refresh_token)
    token_data = await refresh_access_token(refresh_token)

    user.google_access_token = encrypt_token(token_data["access_token"])
    if "refresh_token" in token_data:
        user.google_refresh_token = encrypt_token(token_data["refresh_token"])
    user.token_expiry = datetime.fromtimestamp(
        datetime.now(timezone.utc).timestamp() + token_data.get("expires_in", 3600),
        tz=timezone.utc,
    )
    await db.commit()
    return token_data["access_token"]


async def get_or_create_user(db: AsyncSession, email: str, token_data: dict) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(email=email)
        db.add(user)

    user.google_access_token = encrypt_token(token_data["access_token"])
    if "refresh_token" in token_data:
        user.google_refresh_token = encrypt_token(token_data["refresh_token"])
    user.token_expiry = datetime.fromtimestamp(
        datetime.now(timezone.utc).timestamp() + token_data.get("expires_in", 3600),
        tz=timezone.utc,
    )
    await db.commit()
    await db.refresh(user)
    return user
