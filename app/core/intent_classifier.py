from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from openai import AsyncOpenAI

from app.config import get_settings
from app.schemas.query import ClassifiedIntent
from app.cache.redis_client import cache_get_json, cache_set_json

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """You are an intent classifier for a Google Workspace orchestrator.
Given a user query, classify it into a structured intent.

Current datetime: {current_time}
User timezone: {timezone}

Previous queries in this conversation (most recent first):
{conversation_context}

You MUST respond with valid JSON matching this schema:
{{
  "services": ["gmail", "gcal", "drive"],  // which services are needed
  "intent": "string",                       // e.g. "cancel_flight", "prepare_meeting", "search_emails"
  "entities": {{}},                         // extracted entities: names, emails, dates, keywords
  "steps": [],                              // ordered list of step descriptions
  "ambiguities": [],                        // things that need clarification
  "confidence": 0.0                         // 0.0-1.0 confidence score
}}

Rules:
- "services" must only contain: "gmail", "gcal", "drive"
- Extract temporal references (next week, tomorrow, last month) into absolute dates in entities
- For pronouns or references like "that email", "the meeting", resolve using conversation context
- If a query is ambiguous (e.g. "Move the meeting with John" — which John?), list ambiguities
- Steps should be concrete actions like "search_gmail_for_booking", "find_calendar_event"
- Confidence should reflect how certain you are about the classification

Examples:

Query: "What's on my calendar next week?"
Response:
{{
  "services": ["gcal"],
  "intent": "search_events",
  "entities": {{"date_range": {{"from": "2026-03-02", "to": "2026-03-08"}}}},
  "steps": ["search_calendar_events_next_week"],
  "ambiguities": [],
  "confidence": 0.95
}}

Query: "Cancel my Turkish Airlines flight"
Response:
{{
  "services": ["gmail", "gcal"],
  "intent": "cancel_flight",
  "entities": {{"airline": "Turkish Airlines"}},
  "steps": ["search_gmail_for_booking", "find_calendar_event", "extract_booking_reference", "draft_cancellation_email"],
  "ambiguities": [],
  "confidence": 0.9
}}

Query: "Prepare for tomorrow's client meeting with Acme Corp"
Response:
{{
  "services": ["gcal", "gmail", "drive"],
  "intent": "prepare_meeting",
  "entities": {{"company": "Acme Corp", "date": "tomorrow"}},
  "steps": ["find_calendar_event_tomorrow_acme", "search_emails_acme_corp", "search_drive_acme_documents"],
  "ambiguities": [],
  "confidence": 0.9
}}

Query: "Move the meeting with John"
Response:
{{
  "services": ["gcal"],
  "intent": "update_event",
  "entities": {{"attendee_name": "John"}},
  "steps": ["search_calendar_events_with_john"],
  "ambiguities": ["Which John? Multiple contacts may match.", "When should the meeting be moved to?"],
  "confidence": 0.4
}}

Query: "Find events next week that conflict with my out-of-office doc"
Response:
{{
  "services": ["gcal", "drive"],
  "intent": "find_conflicts",
  "entities": {{"date_range": {{"from": "2026-03-02", "to": "2026-03-08"}}, "document_type": "out-of-office"}},
  "steps": ["search_drive_ooo_document", "extract_ooo_dates", "search_calendar_next_week", "find_conflicting_events"],
  "ambiguities": [],
  "confidence": 0.85
}}
"""

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def classify_intent(
    query: str,
    conversation_context: list[str] | None = None,
    user_timezone: str = "UTC",
) -> ClassifiedIntent:
    cached = await cache_get_json("intent", query)
    if cached is not None:
        return ClassifiedIntent(**cached)

    now = datetime.now(timezone.utc)
    ctx = "\n".join(f"- {q}" for q in (conversation_context or [])) or "(no previous queries)"

    system = SYSTEM_PROMPT.format(
        current_time=now.isoformat(),
        timezone=user_timezone,
        conversation_context=ctx,
    )

    client = _get_client()
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": query},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=1000,
    )

    raw = response.choices[0].message.content
    parsed = json.loads(raw)
    intent = ClassifiedIntent(**parsed)

    await cache_set_json("intent", query, intent.model_dump(), ttl=settings.intent_cache_ttl)
    return intent
