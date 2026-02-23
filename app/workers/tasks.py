from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async function from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.workers.tasks.sync_all_users")
def sync_all_users():
    """Periodic task: sync all users' data."""
    _run_async(_sync_all_users())


async def _sync_all_users():
    from app.db.database import async_session_factory
    from app.models.user import User

    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.google_refresh_token.isnot(None)))
        users = result.scalars().all()
        for user in users:
            sync_user_data.delay(str(user.id))


@celery_app.task(name="app.workers.tasks.sync_user_data", bind=True, max_retries=3)
def sync_user_data(self, user_id: str):
    """Sync Gmail, Calendar, and Drive data for a single user."""
    try:
        _run_async(_sync_user(UUID(user_id)))
    except Exception as exc:
        logger.exception("Sync failed for user %s", user_id)
        self.retry(exc=exc, countdown=60)


async def _sync_user(user_id: UUID):
    from app.db.database import async_session_factory
    from app.models.user import User
    from app.models.cache import SyncStatus, GmailCache, GCalCache, GDriveCache
    from app.services.google_auth import get_valid_token, decrypt_token
    from app.services.embedding import generate_embedding, build_email_text, build_event_text, build_file_text

    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            logger.warning("User %s not found for sync", user_id)
            return

        try:
            access_token = await get_valid_token(user, db)
        except ValueError:
            logger.warning("No valid token for user %s", user_id)
            return

        await _sync_gmail(db, user_id, access_token)
        await _sync_gcal(db, user_id, access_token)
        await _sync_drive(db, user_id, access_token)


async def _sync_gmail(db, user_id: UUID, access_token: str):
    import httpx
    from app.models.cache import GmailCache, SyncStatus
    from app.services.embedding import generate_embedding, build_email_text

    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            "https://www.googleapis.com/gmail/v1/users/me/messages",
            headers=headers,
            params={"maxResults": 50},
        )
        if resp.status_code != 200:
            logger.error("Gmail sync failed: %s", resp.text)
            return

        messages = resp.json().get("messages", [])
        for msg in messages:
            msg_resp = await client.get(
                f"https://www.googleapis.com/gmail/v1/users/me/messages/{msg['id']}",
                headers=headers,
                params={"format": "metadata"},
            )
            if msg_resp.status_code != 200:
                continue

            data = msg_resp.json()
            hdrs = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}

            text = build_email_text(
                hdrs.get("Subject", ""),
                hdrs.get("From", ""),
                data.get("snippet", ""),
            )
            embedding = await generate_embedding(text)

            existing = await db.execute(
                select(GmailCache).where(
                    GmailCache.user_id == user_id,
                    GmailCache.email_id == msg["id"],
                )
            )
            cache_entry = existing.scalar_one_or_none()

            if cache_entry:
                cache_entry.subject = hdrs.get("Subject", "")
                cache_entry.sender = hdrs.get("From", "")
                cache_entry.body_preview = data.get("snippet", "")
                cache_entry.embedding = embedding
                cache_entry.synced_at = datetime.now(timezone.utc)
            else:
                cache_entry = GmailCache(
                    user_id=user_id,
                    email_id=msg["id"],
                    subject=hdrs.get("Subject", ""),
                    sender=hdrs.get("From", ""),
                    body_preview=data.get("snippet", ""),
                    embedding=embedding,
                    received_at=datetime.now(timezone.utc),
                    synced_at=datetime.now(timezone.utc),
                )
                db.add(cache_entry)

        await _update_sync_status(db, user_id, "gmail")
        await db.commit()


async def _sync_gcal(db, user_id: UUID, access_token: str):
    import httpx
    from app.models.cache import GCalCache
    from app.services.embedding import generate_embedding, build_event_text

    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers=headers,
            params={"maxResults": 100, "singleEvents": "true", "orderBy": "startTime",
                     "timeMin": datetime.now(timezone.utc).isoformat()},
        )
        if resp.status_code != 200:
            logger.error("GCal sync failed: %s", resp.text)
            return

        events = resp.json().get("items", [])
        for ev in events:
            attendees = [a.get("email", "") for a in ev.get("attendees", [])]
            text = build_event_text(ev.get("summary", ""), ev.get("description"), attendees)
            embedding = await generate_embedding(text)

            start = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date"))
            end = ev.get("end", {}).get("dateTime", ev.get("end", {}).get("date"))

            existing = await db.execute(
                select(GCalCache).where(
                    GCalCache.user_id == user_id,
                    GCalCache.event_id == ev["id"],
                )
            )
            cache_entry = existing.scalar_one_or_none()

            if cache_entry:
                cache_entry.title = ev.get("summary", "")
                cache_entry.description = ev.get("description", "")
                cache_entry.start_time = datetime.fromisoformat(start) if start else None
                cache_entry.end_time = datetime.fromisoformat(end) if end else None
                cache_entry.attendees = {"list": ev.get("attendees", [])}
                cache_entry.embedding = embedding
                cache_entry.synced_at = datetime.now(timezone.utc)
            else:
                cache_entry = GCalCache(
                    user_id=user_id,
                    event_id=ev["id"],
                    title=ev.get("summary", ""),
                    description=ev.get("description", ""),
                    start_time=datetime.fromisoformat(start) if start else None,
                    end_time=datetime.fromisoformat(end) if end else None,
                    attendees={"list": ev.get("attendees", [])},
                    location=ev.get("location", ""),
                    embedding=embedding,
                    synced_at=datetime.now(timezone.utc),
                )
                db.add(cache_entry)

        await _update_sync_status(db, user_id, "gcal")
        await db.commit()


async def _sync_drive(db, user_id: UUID, access_token: str):
    import httpx
    from app.models.cache import GDriveCache
    from app.services.embedding import generate_embedding, build_file_text

    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            "https://www.googleapis.com/drive/v3/files",
            headers=headers,
            params={
                "pageSize": 100,
                "fields": "files(id,name,mimeType,modifiedTime,description)",
                "q": "trashed = false",
                "orderBy": "modifiedTime desc",
            },
        )
        if resp.status_code != 200:
            logger.error("Drive sync failed: %s", resp.text)
            return

        files = resp.json().get("files", [])
        for f in files:
            text = build_file_text(f.get("name", ""), f.get("mimeType"), f.get("description"))
            embedding = await generate_embedding(text)

            existing = await db.execute(
                select(GDriveCache).where(
                    GDriveCache.user_id == user_id,
                    GDriveCache.file_id == f["id"],
                )
            )
            cache_entry = existing.scalar_one_or_none()

            mod_time = f.get("modifiedTime")
            modified_at = datetime.fromisoformat(mod_time) if mod_time else None

            if cache_entry:
                cache_entry.name = f.get("name", "")
                cache_entry.mime_type = f.get("mimeType", "")
                cache_entry.content_preview = f.get("description", "")
                cache_entry.modified_at = modified_at
                cache_entry.embedding = embedding
                cache_entry.synced_at = datetime.now(timezone.utc)
            else:
                cache_entry = GDriveCache(
                    user_id=user_id,
                    file_id=f["id"],
                    name=f.get("name", ""),
                    mime_type=f.get("mimeType", ""),
                    content_preview=f.get("description", ""),
                    modified_at=modified_at,
                    embedding=embedding,
                    synced_at=datetime.now(timezone.utc),
                )
                db.add(cache_entry)

        await _update_sync_status(db, user_id, "drive")
        await db.commit()


async def _update_sync_status(db, user_id: UUID, service: str):
    from app.models.cache import SyncStatus

    existing = await db.execute(
        select(SyncStatus).where(
            SyncStatus.user_id == user_id,
            SyncStatus.service == service,
        )
    )
    status = existing.scalar_one_or_none()
    if status:
        status.last_sync_at = datetime.now(timezone.utc)
        status.status = "completed"
    else:
        db.add(SyncStatus(
            user_id=user_id,
            service=service,
            last_sync_at=datetime.now(timezone.utc),
            status="completed",
        ))
