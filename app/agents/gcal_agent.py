from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.agents.base import BaseAgent
from app.services.vector_search import hybrid_search_events

logger = logging.getLogger(__name__)

GCAL_API = "https://www.googleapis.com/calendar/v3"


class GCalAgent(BaseAgent):
    SERVICE_NAME = "gcal"

    async def search(self, query: str, **kwargs) -> list[dict]:
        return await self.search_events(query=query, **kwargs)

    async def get_context(self, resource_id: str) -> dict:
        return await self.get_event(event_id=resource_id)

    async def search_events(
        self,
        query: str | None = None,
        keyword: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        date: str | None = None,
        attendee: str | None = None,
        attendee_email: str | None = None,
        limit: int = 10,
        **kwargs,
    ) -> list[dict]:
        search_query = keyword or query or ""

        df = datetime.fromisoformat(date_from) if date_from else None
        dt = datetime.fromisoformat(date_to) if date_to else None

        if date and not df:
            if date == "tomorrow":
                df = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0) + timedelta(days=1)
                dt = df + timedelta(days=1)
            elif date == "today":
                df = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
                dt = df + timedelta(days=1)

        attendees_filter = []
        if attendee_email:
            attendees_filter.append(attendee_email)

        results = await hybrid_search_events(
            self.db, self.user_id, search_query,
            date_from=df, date_to=dt,
            attendees=attendees_filter or None,
            limit=limit,
        )

        if not results:
            results = await self._api_search(
                query=search_query, time_min=df, time_max=dt, max_results=limit,
            )

        return results

    async def _api_search(
        self,
        query: str | None = None,
        time_min: datetime | None = None,
        time_max: datetime | None = None,
        max_results: int = 10,
    ) -> list[dict]:
        params: dict = {"maxResults": max_results, "singleEvents": "true", "orderBy": "startTime"}
        if query:
            params["q"] = query
        if time_min:
            params["timeMin"] = time_min.isoformat()
        if time_max:
            params["timeMax"] = time_max.isoformat()

        data = await self._request("GET", f"{GCAL_API}/calendars/primary/events", params=params)

        return [
            {
                "event_id": ev["id"],
                "title": ev.get("summary", ""),
                "description": ev.get("description", ""),
                "start_time": ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date")),
                "end_time": ev.get("end", {}).get("dateTime", ev.get("end", {}).get("date")),
                "attendees": [a.get("email") for a in ev.get("attendees", [])],
                "location": ev.get("location", ""),
                "status": ev.get("status", ""),
            }
            for ev in data.get("items", [])
        ]

    async def get_event(self, event_id: str, **kwargs) -> dict:
        data = await self._request("GET", f"{GCAL_API}/calendars/primary/events/{event_id}")
        return {
            "event_id": data["id"],
            "title": data.get("summary", ""),
            "description": data.get("description", ""),
            "start_time": data.get("start", {}).get("dateTime"),
            "end_time": data.get("end", {}).get("dateTime"),
            "attendees": [a.get("email") for a in data.get("attendees", [])],
            "location": data.get("location", ""),
            "status": data.get("status", ""),
        }

    async def create_event(
        self,
        title: str,
        start: str,
        end: str,
        attendees: list[str] | None = None,
        description: str | None = None,
        **kwargs,
    ) -> dict:
        body: dict = {
            "summary": title,
            "start": {"dateTime": start},
            "end": {"dateTime": end},
        }
        if description:
            body["description"] = description
        if attendees:
            body["attendees"] = [{"email": e} for e in attendees]

        data = await self._request("POST", f"{GCAL_API}/calendars/primary/events", json_body=body)
        return {"event_id": data["id"], "title": title, "status": "created"}

    async def update_event(
        self,
        event_id: str,
        title: str | None = None,
        start: str | None = None,
        end: str | None = None,
        description: str | None = None,
        **kwargs,
    ) -> dict:
        body: dict = {}
        if title:
            body["summary"] = title
        if start:
            body["start"] = {"dateTime": start}
        if end:
            body["end"] = {"dateTime": end}
        if description:
            body["description"] = description

        data = await self._request("PATCH", f"{GCAL_API}/calendars/primary/events/{event_id}", json_body=body)
        return {"event_id": data["id"], "status": "updated"}

    async def delete_event(self, event_id: str, **kwargs) -> dict:
        await self._request("DELETE", f"{GCAL_API}/calendars/primary/events/{event_id}")
        return {"event_id": event_id, "status": "deleted"}
