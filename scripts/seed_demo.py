#!/usr/bin/env python3
"""Seed the database with a demo user and cached data with embeddings.

Usage:
    uv run python scripts/seed_demo.py
"""

import asyncio
import sys
import os
from datetime import datetime, timezone
from uuid import UUID

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEMO_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
DEMO_EMAIL = "demo@workspace.dev"
DEMO_TOKEN = "demo-access-token"


async def main():
    from app.config import get_settings
    settings = get_settings()

    if not settings.openai_api_key or settings.openai_api_key == "your-openai-key":
        print("ERROR: Set OPENAI_API_KEY in .env to generate embeddings.")
        print("       Embeddings are required for vector search to work in the demo.")
        sys.exit(1)

    from sqlalchemy import select, text
    from app.db.database import async_session_factory, engine
    from app.models.user import User
    from app.models.cache import GmailCache, GCalCache, GDriveCache, SyncStatus
    from app.services.embedding import (
        generate_embedding,
        build_email_text,
        build_event_text,
        build_file_text,
    )
    from app.agents.mock_data import MOCK_EMAILS, MOCK_EVENTS, MOCK_FILES
    from app.services.google_auth import encrypt_token

    print("Connecting to database...")
    async with async_session_factory() as db:
        # 1. Create demo user
        result = await db.execute(select(User).where(User.id == DEMO_USER_ID))
        user = result.scalar_one_or_none()
        if user:
            print(f"Demo user already exists: {user.email}")
        else:
            user = User(
                id=DEMO_USER_ID,
                email=DEMO_EMAIL,
                google_access_token=encrypt_token(DEMO_TOKEN),
                google_refresh_token=encrypt_token("demo-refresh-token"),
                token_expiry=datetime(2099, 1, 1, tzinfo=timezone.utc),
            )
            db.add(user)
            await db.commit()
            print(f"Created demo user: {DEMO_EMAIL}")

        # 2. Seed Gmail cache
        print("\nSeeding Gmail cache...")
        for i, email in enumerate(MOCK_EMAILS):
            existing = await db.execute(
                select(GmailCache).where(
                    GmailCache.user_id == DEMO_USER_ID,
                    GmailCache.email_id == email["email_id"],
                )
            )
            if existing.scalar_one_or_none():
                print(f"  [{i+1}/{len(MOCK_EMAILS)}] Skip (exists): {email['subject'][:50]}")
                continue

            text_for_embed = build_email_text(
                email["subject"], email["sender"], email.get("body_preview", email.get("snippet", ""))
            )
            print(f"  [{i+1}/{len(MOCK_EMAILS)}] Embedding: {email['subject'][:50]}...")
            embedding = await generate_embedding(text_for_embed)

            received = datetime.fromisoformat(email["received_at"]) if email.get("received_at") else datetime.now(timezone.utc)
            entry = GmailCache(
                user_id=DEMO_USER_ID,
                email_id=email["email_id"],
                subject=email["subject"],
                sender=email["sender"],
                recipients=email.get("recipients"),
                body_preview=email.get("body_preview", email.get("snippet", "")),
                embedding=embedding,
                received_at=received,
                synced_at=datetime.now(timezone.utc),
            )
            db.add(entry)

        await db.commit()
        print(f"  Gmail cache: {len(MOCK_EMAILS)} emails seeded.")

        # 3. Seed GCal cache
        print("\nSeeding GCal cache...")
        for i, event in enumerate(MOCK_EVENTS):
            existing = await db.execute(
                select(GCalCache).where(
                    GCalCache.user_id == DEMO_USER_ID,
                    GCalCache.event_id == event["event_id"],
                )
            )
            if existing.scalar_one_or_none():
                print(f"  [{i+1}/{len(MOCK_EVENTS)}] Skip (exists): {event['title'][:50]}")
                continue

            text_for_embed = build_event_text(
                event["title"], event.get("description"), event.get("attendees")
            )
            print(f"  [{i+1}/{len(MOCK_EVENTS)}] Embedding: {event['title'][:50]}...")
            embedding = await generate_embedding(text_for_embed)

            start = datetime.fromisoformat(event["start_time"]) if event.get("start_time") else None
            end = datetime.fromisoformat(event["end_time"]) if event.get("end_time") else None
            entry = GCalCache(
                user_id=DEMO_USER_ID,
                event_id=event["event_id"],
                title=event["title"],
                description=event.get("description"),
                start_time=start,
                end_time=end,
                attendees={"list": [{"email": a} for a in event.get("attendees", [])]},
                location=event.get("location"),
                embedding=embedding,
                synced_at=datetime.now(timezone.utc),
            )
            db.add(entry)

        await db.commit()
        print(f"  GCal cache: {len(MOCK_EVENTS)} events seeded.")

        # 4. Seed Drive cache
        print("\nSeeding Drive cache...")
        for i, file in enumerate(MOCK_FILES):
            existing = await db.execute(
                select(GDriveCache).where(
                    GDriveCache.user_id == DEMO_USER_ID,
                    GDriveCache.file_id == file["file_id"],
                )
            )
            if existing.scalar_one_or_none():
                print(f"  [{i+1}/{len(MOCK_FILES)}] Skip (exists): {file['name'][:50]}")
                continue

            text_for_embed = build_file_text(
                file["name"], file.get("mime_type"), file.get("content_preview")
            )
            print(f"  [{i+1}/{len(MOCK_FILES)}] Embedding: {file['name'][:50]}...")
            embedding = await generate_embedding(text_for_embed)

            modified = datetime.fromisoformat(file["modified_at"]) if file.get("modified_at") else None
            entry = GDriveCache(
                user_id=DEMO_USER_ID,
                file_id=file["file_id"],
                name=file["name"],
                mime_type=file.get("mime_type"),
                content_preview=file.get("content_preview"),
                modified_at=modified,
                embedding=embedding,
                synced_at=datetime.now(timezone.utc),
            )
            db.add(entry)

        await db.commit()
        print(f"  Drive cache: {len(MOCK_FILES)} files seeded.")

        # 5. Set sync status
        for svc in ["gmail", "gcal", "drive"]:
            existing = await db.execute(
                select(SyncStatus).where(
                    SyncStatus.user_id == DEMO_USER_ID,
                    SyncStatus.service == svc,
                )
            )
            if not existing.scalar_one_or_none():
                db.add(SyncStatus(
                    user_id=DEMO_USER_ID,
                    service=svc,
                    last_sync_at=datetime.now(timezone.utc),
                    status="completed",
                ))
        await db.commit()

    print("\n" + "=" * 60)
    print("DEMO SEED COMPLETE")
    print("=" * 60)
    print(f"  User ID:  {DEMO_USER_ID}")
    print(f"  Email:    {DEMO_EMAIL}")
    print(f"  Emails:   {len(MOCK_EMAILS)}")
    print(f"  Events:   {len(MOCK_EVENTS)}")
    print(f"  Files:    {len(MOCK_FILES)}")
    print()
    print("Start the server:")
    print("  uv run uvicorn app.main:app --reload")
    print()
    print("Then run the demo:")
    print("  uv run python scripts/run_demo.py")
    print()


if __name__ == "__main__":
    asyncio.run(main())
