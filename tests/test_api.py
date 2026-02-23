import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.user import User


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_query_endpoint_missing_user_header():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/query", json={"query": "test"})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_query_endpoint_rate_limited():
    user_id = str(uuid.uuid4())

    with patch("app.api.v1.query.rate_limit_check", new_callable=AsyncMock, return_value=False):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/query",
                json={"query": "What's on my calendar?"},
                headers={"x-user-id": user_id},
            )
            assert resp.status_code == 429


@pytest.mark.asyncio
async def test_query_endpoint_user_not_found():
    user_id = str(uuid.uuid4())

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.close = AsyncMock()

    async def mock_get_db():
        yield mock_db

    from app.db.database import get_db

    with patch("app.api.v1.query.rate_limit_check", new_callable=AsyncMock, return_value=True), \
         patch("app.api.v1.query.get_conversation_context", new_callable=AsyncMock, return_value=[]), \
         patch("app.api.v1.query.store_conversation_context", new_callable=AsyncMock):
        app.dependency_overrides[get_db] = mock_get_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/query",
                    json={"query": "What's on my calendar?"},
                    headers={"x-user-id": user_id},
                )
                assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_google_auth_redirect():
    with patch("app.api.v1.auth.get_auth_url", return_value="https://accounts.google.com/o/oauth2/v2/auth?test"):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
            resp = await client.get("/api/v1/auth/google")
            assert resp.status_code == 307
            assert "accounts.google.com" in resp.headers.get("location", "")
