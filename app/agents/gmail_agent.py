from __future__ import annotations

import base64
import logging
from datetime import datetime
from email.mime.text import MIMEText

from app.agents.base import BaseAgent
from app.services.vector_search import hybrid_search_emails

logger = logging.getLogger(__name__)

GMAIL_API = "https://www.googleapis.com/gmail/v1/users/me"


class GmailAgent(BaseAgent):
    SERVICE_NAME = "gmail"

    async def search(self, query: str, **kwargs) -> list[dict]:
        return await self.search_emails(query=query, **kwargs)

    async def get_context(self, resource_id: str) -> dict:
        return await self.get_email(email_id=resource_id)

    async def search_emails(
        self,
        query: str | None = None,
        keyword: str | None = None,
        sender: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 5,
        **kwargs,
    ) -> list[dict]:
        """Hybrid search: vector similarity on cache + metadata filters."""
        search_query = keyword or query or ""

        # Parse date strings to datetime
        df = datetime.fromisoformat(date_from) if date_from else None
        dt = datetime.fromisoformat(date_to) if date_to else None

        results = await hybrid_search_emails(
            self.db, self.user_id, search_query,
            sender=sender, date_from=df, date_to=dt, limit=limit,
        )

        if not results:
            # Fallback: direct Gmail API search
            results = await self._api_search(search_query, sender=sender, max_results=limit)

        return results

    async def _api_search(
        self,
        query: str,
        sender: str | None = None,
        max_results: int = 5,
    ) -> list[dict]:
        q_parts = [query] if query else []
        if sender:
            q_parts.append(f"from:{sender}")
        q_string = " ".join(q_parts)

        data = await self._request(
            "GET",
            f"{GMAIL_API}/messages",
            params={"q": q_string, "maxResults": max_results},
        )

        messages = data.get("messages", [])
        results = []
        for msg in messages[:max_results]:
            detail = await self.get_email(msg["id"])
            results.append(detail)
        return results

    async def get_email(self, email_id: str, **kwargs) -> dict:
        data = await self._request("GET", f"{GMAIL_API}/messages/{email_id}", params={"format": "metadata"})

        headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
        return {
            "email_id": data["id"],
            "thread_id": data.get("threadId"),
            "subject": headers.get("Subject", ""),
            "sender": headers.get("From", ""),
            "to": headers.get("To", ""),
            "date": headers.get("Date", ""),
            "snippet": data.get("snippet", ""),
            "labels": data.get("labelIds", []),
        }

    async def draft_email(
        self,
        to: str | None = None,
        subject: str | None = None,
        body: str | None = None,
        keyword: str | None = None,
        **kwargs,
    ) -> dict:
        # If called as part of a multi-step plan, extract context
        context = kwargs.get("_context", {})
        if not to and context:
            for ctx_data in context.values():
                if isinstance(ctx_data, list) and ctx_data:
                    to = to or ctx_data[0].get("sender", "")
                    subject = subject or f"Re: {ctx_data[0].get('subject', '')}"
                elif isinstance(ctx_data, dict):
                    to = to or ctx_data.get("sender", "")
                    subject = subject or f"Re: {ctx_data.get('subject', '')}"

        msg = MIMEText(body or "")
        msg["to"] = to or ""
        msg["subject"] = subject or ""

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        data = await self._request(
            "POST",
            f"{GMAIL_API}/drafts",
            json_body={"message": {"raw": raw}},
        )
        return {
            "draft_id": data.get("id"),
            "to": to,
            "subject": subject,
            "status": "drafted",
        }

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        **kwargs,
    ) -> dict:
        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        data = await self._request(
            "POST",
            f"{GMAIL_API}/messages/send",
            json_body={"raw": raw},
        )
        return {
            "message_id": data.get("id"),
            "to": to,
            "subject": subject,
            "status": "sent",
        }

    async def update_labels(
        self,
        email_id: str,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
        **kwargs,
    ) -> dict:
        body = {}
        if add_labels:
            body["addLabelIds"] = add_labels
        if remove_labels:
            body["removeLabelIds"] = remove_labels

        await self._request("POST", f"{GMAIL_API}/messages/{email_id}/modify", json_body=body)
        return {"email_id": email_id, "status": "labels_updated"}
