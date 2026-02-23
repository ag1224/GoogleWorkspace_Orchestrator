from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.cache import SyncStatus
from app.models.user import User
from app.schemas.query import SyncStatusResponse, SyncTriggerResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/trigger", response_model=SyncTriggerResponse)
async def trigger_sync(
    db: AsyncSession = Depends(get_db),
    x_user_id: str = Header(...),
):
    """Trigger a manual sync for all Google services."""
    user_id = uuid.UUID(x_user_id)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Dispatch Celery tasks
    from app.workers.tasks import sync_user_data
    sync_user_data.delay(str(user_id))

    return SyncTriggerResponse(
        message="Sync triggered for all services",
        services=["gmail", "gcal", "drive"],
    )


@router.get("/status", response_model=list[SyncStatusResponse])
async def get_sync_status(
    db: AsyncSession = Depends(get_db),
    x_user_id: str = Header(...),
):
    """Get last sync timestamps per service."""
    user_id = uuid.UUID(x_user_id)

    result = await db.execute(
        select(SyncStatus).where(SyncStatus.user_id == user_id)
    )
    statuses = result.scalars().all()

    if not statuses:
        return [
            SyncStatusResponse(service=svc, last_sync_at=None, status="never_synced")
            for svc in ["gmail", "gcal", "drive"]
        ]

    return [
        SyncStatusResponse(
            service=s.service,
            last_sync_at=s.last_sync_at,
            status=s.status,
        )
        for s in statuses
    ]
