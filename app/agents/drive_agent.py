from __future__ import annotations

import logging
from datetime import datetime

from app.agents.base import BaseAgent
from app.services.vector_search import hybrid_search_files

logger = logging.getLogger(__name__)

DRIVE_API = "https://www.googleapis.com/drive/v3"


class DriveAgent(BaseAgent):
    SERVICE_NAME = "drive"

    async def search(self, query: str, **kwargs) -> list[dict]:
        return await self.search_files(query=query, **kwargs)

    async def get_context(self, resource_id: str) -> dict:
        return await self.get_file(file_id=resource_id)

    async def search_files(
        self,
        query: str | None = None,
        keyword: str | None = None,
        mime_type: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 5,
        **kwargs,
    ) -> list[dict]:
        search_query = keyword or query or ""

        df = datetime.fromisoformat(date_from) if date_from else None
        dt = datetime.fromisoformat(date_to) if date_to else None

        results = await hybrid_search_files(
            self.db, self.user_id, search_query,
            mime_type=mime_type, date_from=df, date_to=dt, limit=limit,
        )

        if not results:
            results = await self._api_search(query=search_query, mime_type=mime_type, max_results=limit)

        return results

    async def _api_search(
        self,
        query: str | None = None,
        mime_type: str | None = None,
        max_results: int = 10,
    ) -> list[dict]:
        q_parts = []
        if query:
            q_parts.append(f"fullText contains '{query}'")
        if mime_type:
            q_parts.append(f"mimeType = '{mime_type}'")
        q_parts.append("trashed = false")

        params = {
            "q": " and ".join(q_parts),
            "pageSize": max_results,
            "fields": "files(id,name,mimeType,modifiedTime,description)",
        }

        data = await self._request("GET", f"{DRIVE_API}/files", params=params)

        return [
            {
                "file_id": f["id"],
                "name": f.get("name", ""),
                "mime_type": f.get("mimeType", ""),
                "modified_at": f.get("modifiedTime"),
                "description": f.get("description", ""),
            }
            for f in data.get("files", [])
        ]

    async def get_file(self, file_id: str, **kwargs) -> dict:
        data = await self._request(
            "GET",
            f"{DRIVE_API}/files/{file_id}",
            params={"fields": "id,name,mimeType,modifiedTime,description,webViewLink,owners"},
        )
        return {
            "file_id": data["id"],
            "name": data.get("name", ""),
            "mime_type": data.get("mimeType", ""),
            "modified_at": data.get("modifiedTime"),
            "description": data.get("description", ""),
            "web_link": data.get("webViewLink"),
            "owners": [o.get("emailAddress") for o in data.get("owners", [])],
        }

    async def share_file(
        self,
        file_id: str,
        email: str,
        role: str = "reader",
        **kwargs,
    ) -> dict:
        await self._request(
            "POST",
            f"{DRIVE_API}/files/{file_id}/permissions",
            json_body={"type": "user", "role": role, "emailAddress": email},
        )
        return {"file_id": file_id, "shared_with": email, "role": role, "status": "shared"}

    async def create_folder(
        self,
        name: str,
        parent_id: str | None = None,
        **kwargs,
    ) -> dict:
        body: dict = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            body["parents"] = [parent_id]

        data = await self._request("POST", f"{DRIVE_API}/files", json_body=body)
        return {"file_id": data["id"], "name": name, "status": "folder_created"}

    async def move_file(
        self,
        file_id: str,
        destination_folder_id: str,
        **kwargs,
    ) -> dict:
        # Get current parents
        file_data = await self._request(
            "GET",
            f"{DRIVE_API}/files/{file_id}",
            params={"fields": "parents"},
        )
        current_parents = ",".join(file_data.get("parents", []))

        await self._request(
            "PATCH",
            f"{DRIVE_API}/files/{file_id}",
            params={"addParents": destination_folder_id, "removeParents": current_parents},
        )
        return {"file_id": file_id, "destination": destination_folder_id, "status": "moved"}
