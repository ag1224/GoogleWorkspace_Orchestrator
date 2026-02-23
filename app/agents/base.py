from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class BaseAgent(ABC):
    """Abstract base for all Google Workspace agents."""

    SERVICE_NAME: str = ""

    def __init__(self, access_token: str, user_id: UUID, db: AsyncSession):
        self.access_token = access_token
        self.user_id = user_id
        self.db = db

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> dict:
        """Make an HTTP request to Google API with retry + exponential backoff."""
        last_exc: Exception | None = None
        for attempt in range(settings.google_api_retry_attempts):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.request(
                        method,
                        url,
                        headers=self._headers(),
                        params=params,
                        json=json_body,
                    )
                    if resp.status_code == 429:
                        delay = settings.google_api_retry_base_delay * (2 ** attempt)
                        logger.warning("Rate limited on %s, retrying in %.1fs", url, delay)
                        await asyncio.sleep(delay)
                        continue
                    resp.raise_for_status()
                    return resp.json()
            except httpx.HTTPStatusError as e:
                last_exc = e
                if e.response.status_code >= 500:
                    delay = settings.google_api_retry_base_delay * (2 ** attempt)
                    logger.warning("Server error %s on %s, retrying in %.1fs", e.response.status_code, url, delay)
                    await asyncio.sleep(delay)
                    continue
                raise
            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                last_exc = e
                delay = settings.google_api_retry_base_delay * (2 ** attempt)
                logger.warning("Connection error on %s, retrying in %.1fs", url, delay)
                await asyncio.sleep(delay)
                continue

        raise last_exc or RuntimeError(f"Request to {url} failed after retries")

    async def execute_action(self, action: str, params: dict) -> dict | list | str | None:
        """Dispatch to the appropriate method based on action name."""
        method = getattr(self, action, None)
        if method is None:
            raise ValueError(f"Agent {self.SERVICE_NAME} has no action '{action}'")
        return await method(**{k: v for k, v in params.items() if not k.startswith("_")})

    @abstractmethod
    async def search(self, query: str, **kwargs) -> list[dict]:
        ...

    @abstractmethod
    async def get_context(self, resource_id: str) -> dict:
        ...
