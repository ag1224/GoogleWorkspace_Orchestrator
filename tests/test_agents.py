import uuid
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.agents.gmail_agent import GmailAgent
from app.agents.gcal_agent import GCalAgent
from app.agents.drive_agent import DriveAgent


@pytest.fixture
def gmail_agent(mock_db, sample_user_id, sample_access_token):
    return GmailAgent(access_token=sample_access_token, user_id=sample_user_id, db=mock_db)


@pytest.fixture
def gcal_agent(mock_db, sample_user_id, sample_access_token):
    return GCalAgent(access_token=sample_access_token, user_id=sample_user_id, db=mock_db)


@pytest.fixture
def drive_agent(mock_db, sample_user_id, sample_access_token):
    return DriveAgent(access_token=sample_access_token, user_id=sample_user_id, db=mock_db)


@pytest.mark.asyncio
async def test_gmail_search_uses_vector_search(gmail_agent):
    mock_results = [
        {"email_id": "e1", "subject": "Flight Booking", "sender": "airline@test.com", "similarity": 0.92}
    ]

    with patch("app.agents.gmail_agent.hybrid_search_emails", new_callable=AsyncMock, return_value=mock_results):
        results = await gmail_agent.search_emails(query="flight booking")
        assert len(results) == 1
        assert results[0]["subject"] == "Flight Booking"


@pytest.mark.asyncio
async def test_gmail_search_falls_back_to_api(gmail_agent):
    with patch("app.agents.gmail_agent.hybrid_search_emails", new_callable=AsyncMock, return_value=[]), \
         patch.object(gmail_agent, "_api_search", new_callable=AsyncMock, return_value=[{"email_id": "e2"}]):
        results = await gmail_agent.search_emails(query="rare email")
        assert len(results) == 1


@pytest.mark.asyncio
async def test_gmail_execute_action_dispatches(gmail_agent):
    with patch.object(gmail_agent, "search_emails", new_callable=AsyncMock, return_value=[]) as mock_search:
        await gmail_agent.execute_action("search_emails", {"query": "test"})
        mock_search.assert_called_once_with(query="test")


@pytest.mark.asyncio
async def test_gcal_search_events(gcal_agent):
    mock_results = [
        {"event_id": "ev1", "title": "Team Meeting", "start_time": "2026-03-01T10:00:00Z", "similarity": 0.88}
    ]

    with patch("app.agents.gcal_agent.hybrid_search_events", new_callable=AsyncMock, return_value=mock_results):
        results = await gcal_agent.search_events(query="team meeting")
        assert len(results) == 1
        assert results[0]["title"] == "Team Meeting"


@pytest.mark.asyncio
async def test_drive_search_files(drive_agent):
    mock_results = [
        {"file_id": "f1", "name": "Q4 Report.pdf", "mime_type": "application/pdf", "similarity": 0.85}
    ]

    with patch("app.agents.drive_agent.hybrid_search_files", new_callable=AsyncMock, return_value=mock_results):
        results = await drive_agent.search_files(query="Q4 report")
        assert len(results) == 1
        assert results[0]["name"] == "Q4 Report.pdf"


@pytest.mark.asyncio
async def test_agent_retry_on_server_error(gmail_agent):
    """Verify BaseAgent._request retries on 500 errors with backoff."""
    import httpx

    call_count = 0

    async def mock_send(self, request, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(500, request=request, json={"error": "server error"})
        return httpx.Response(200, request=request, json={"messages": []})

    with patch("httpx.AsyncClient.send", new=mock_send), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        result = await gmail_agent._api_search("test")
        assert call_count == 3


@pytest.mark.asyncio
async def test_agent_unknown_action_raises(gmail_agent):
    with pytest.raises(ValueError, match="has no action"):
        await gmail_agent.execute_action("nonexistent_action", {})
