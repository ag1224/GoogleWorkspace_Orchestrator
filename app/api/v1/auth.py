from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.google_auth import exchange_code, get_auth_url, get_or_create_user, get_user_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/google")
async def google_auth():
    """Redirect to Google OAuth consent screen."""
    url = get_auth_url()
    return RedirectResponse(url=url)


@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle OAuth callback, exchange code for tokens, create/update user."""
    try:
        token_data = await exchange_code(code)
        email = await get_user_email(token_data["access_token"])
        user = await get_or_create_user(db, email, token_data)
        return {
            "user_id": str(user.id),
            "email": user.email,
            "message": "Authentication successful",
        }
    except Exception as e:
        logger.exception("OAuth callback failed")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {e}")
