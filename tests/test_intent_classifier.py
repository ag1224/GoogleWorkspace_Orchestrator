import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.query import ClassifiedIntent


@pytest.fixture
def mock_openai_response():
    def _make(content: dict):
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = json.dumps(content)
        return mock_resp
    return _make


@pytest.mark.asyncio
async def test_classify_single_service_query(mock_openai_response):
    intent_data = {
        "services": ["gcal"],
        "intent": "search_events",
        "entities": {"date_range": {"from": "2026-03-02", "to": "2026-03-08"}},
        "steps": ["search_calendar_events_next_week"],
        "ambiguities": [],
        "confidence": 0.95,
    }

    with patch("app.core.intent_classifier._get_client") as mock_client, \
         patch("app.core.intent_classifier.cache_get_json", return_value=None), \
         patch("app.core.intent_classifier.cache_set_json", new_callable=AsyncMock):
        mock_client.return_value.chat.completions.create = AsyncMock(
            return_value=mock_openai_response(intent_data)
        )

        from app.core.intent_classifier import classify_intent
        result = await classify_intent("What's on my calendar next week?")

        assert isinstance(result, ClassifiedIntent)
        assert result.services == ["gcal"]
        assert result.intent == "search_events"
        assert result.confidence == 0.95
        assert len(result.ambiguities) == 0


@pytest.mark.asyncio
async def test_classify_multi_service_query(mock_openai_response):
    intent_data = {
        "services": ["gmail", "gcal"],
        "intent": "cancel_flight",
        "entities": {"airline": "Turkish Airlines"},
        "steps": ["search_gmail_for_booking", "find_calendar_event", "draft_cancellation_email"],
        "ambiguities": [],
        "confidence": 0.9,
    }

    with patch("app.core.intent_classifier._get_client") as mock_client, \
         patch("app.core.intent_classifier.cache_get_json", return_value=None), \
         patch("app.core.intent_classifier.cache_set_json", new_callable=AsyncMock):
        mock_client.return_value.chat.completions.create = AsyncMock(
            return_value=mock_openai_response(intent_data)
        )

        from app.core.intent_classifier import classify_intent
        result = await classify_intent("Cancel my Turkish Airlines flight")

        assert "gmail" in result.services
        assert "gcal" in result.services
        assert result.intent == "cancel_flight"
        assert len(result.steps) == 3


@pytest.mark.asyncio
async def test_classify_ambiguous_query(mock_openai_response):
    intent_data = {
        "services": ["gcal"],
        "intent": "update_event",
        "entities": {"attendee_name": "John"},
        "steps": ["search_calendar_events_with_john"],
        "ambiguities": ["Which John?", "When should it be moved to?"],
        "confidence": 0.4,
    }

    with patch("app.core.intent_classifier._get_client") as mock_client, \
         patch("app.core.intent_classifier.cache_get_json", return_value=None), \
         patch("app.core.intent_classifier.cache_set_json", new_callable=AsyncMock):
        mock_client.return_value.chat.completions.create = AsyncMock(
            return_value=mock_openai_response(intent_data)
        )

        from app.core.intent_classifier import classify_intent
        result = await classify_intent("Move the meeting with John")

        assert len(result.ambiguities) == 2
        assert result.confidence < 0.5


@pytest.mark.asyncio
async def test_classify_uses_cache():
    cached_data = {
        "services": ["gmail"],
        "intent": "search_emails",
        "entities": {},
        "steps": ["search_emails"],
        "ambiguities": [],
        "confidence": 0.9,
    }

    with patch("app.core.intent_classifier.cache_get_json", return_value=cached_data):
        from app.core.intent_classifier import classify_intent
        result = await classify_intent("Find emails from Sarah")

        assert result.services == ["gmail"]
        assert result.intent == "search_emails"
