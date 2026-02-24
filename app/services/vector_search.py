from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embedding import generate_embedding

logger = logging.getLogger(__name__)


def _temporal_decay(days_ago: float) -> float:
    """Weight recent items higher: score * 1/log(days_ago + 2)."""
    return 1.0 / math.log(days_ago + 2)


async def hybrid_search_emails(
    db: AsyncSession,
    user_id: UUID,
    query: str,
    *,
    sender: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 5,
) -> list[dict]:
    query_embedding = await generate_embedding(query)

    sql = """
        SELECT id, email_id, subject, sender, recipients, body_preview, received_at,
               1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM gmail_cache
        WHERE user_id = :user_id AND embedding IS NOT NULL
    """
    params: dict = {"user_id": str(user_id), "embedding": str(query_embedding)}

    if sender:
        sql += " AND sender ILIKE :sender"
        params["sender"] = f"%{sender}%"
    if date_from:
        sql += " AND received_at >= :date_from"
        params["date_from"] = date_from
    if date_to:
        sql += " AND received_at <= :date_to"
        params["date_to"] = date_to

    sql += " ORDER BY embedding <=> CAST(:embedding AS vector) LIMIT :limit"
    params["limit"] = limit

    result = await db.execute(text(sql), params)
    rows = result.mappings().all()

    now = datetime.now(timezone.utc)
    results = []
    for row in rows:
        days_ago = (now - row["received_at"]).total_seconds() / 86400 if row["received_at"] else 0
        score = float(row["similarity"]) * _temporal_decay(days_ago)
        results.append({
            "id": str(row["id"]),
            "email_id": row["email_id"],
            "subject": row["subject"],
            "sender": row["sender"],
            "body_preview": row["body_preview"],
            "received_at": row["received_at"].isoformat() if row["received_at"] else None,
            "similarity": float(row["similarity"]),
            "score": score,
        })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


async def hybrid_search_events(
    db: AsyncSession,
    user_id: UUID,
    query: str,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    attendees: list[str] | None = None,
    limit: int = 5,
) -> list[dict]:
    query_embedding = await generate_embedding(query)

    sql = """
        SELECT id, event_id, title, description, start_time, end_time, attendees, location,
               1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM gcal_cache
        WHERE user_id = :user_id AND embedding IS NOT NULL
    """
    params: dict = {"user_id": str(user_id), "embedding": str(query_embedding)}

    if date_from:
        sql += " AND start_time >= :date_from"
        params["date_from"] = date_from
    if date_to:
        sql += " AND end_time <= :date_to"
        params["date_to"] = date_to

    sql += " ORDER BY embedding <=> CAST(:embedding AS vector) LIMIT :limit"
    params["limit"] = limit

    result = await db.execute(text(sql), params)
    rows = result.mappings().all()

    results = []
    for row in rows:
        event = {
            "id": str(row["id"]),
            "event_id": row["event_id"],
            "title": row["title"],
            "description": row["description"],
            "start_time": row["start_time"].isoformat() if row["start_time"] else None,
            "end_time": row["end_time"].isoformat() if row["end_time"] else None,
            "attendees": row["attendees"],
            "location": row["location"],
            "similarity": float(row["similarity"]),
        }
        if attendees:
            event_attendees = row["attendees"] or []
            if isinstance(event_attendees, dict):
                event_attendees = [a.get("email", "") for a in event_attendees.get("list", [])]
            if not any(att in str(event_attendees) for att in attendees):
                continue
        results.append(event)
    return results


async def hybrid_search_files(
    db: AsyncSession,
    user_id: UUID,
    query: str,
    *,
    mime_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 5,
) -> list[dict]:
    query_embedding = await generate_embedding(query)

    sql = """
        SELECT id, file_id, name, mime_type, content_preview, modified_at,
               1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM gdrive_cache
        WHERE user_id = :user_id AND embedding IS NOT NULL
    """
    params: dict = {"user_id": str(user_id), "embedding": str(query_embedding)}

    if mime_type:
        sql += " AND mime_type = :mime_type"
        params["mime_type"] = mime_type
    if date_from:
        sql += " AND modified_at >= :date_from"
        params["date_from"] = date_from
    if date_to:
        sql += " AND modified_at <= :date_to"
        params["date_to"] = date_to

    sql += " ORDER BY embedding <=> CAST(:embedding AS vector) LIMIT :limit"
    params["limit"] = limit

    result = await db.execute(text(sql), params)
    rows = result.mappings().all()

    return [
        {
            "id": str(row["id"]),
            "file_id": row["file_id"],
            "name": row["name"],
            "mime_type": row["mime_type"],
            "content_preview": row["content_preview"],
            "modified_at": row["modified_at"].isoformat() if row["modified_at"] else None,
            "similarity": float(row["similarity"]),
        }
        for row in rows
    ]
