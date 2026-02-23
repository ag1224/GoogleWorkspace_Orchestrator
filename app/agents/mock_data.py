"""Canned mock responses for demo mode — realistic Google Workspace data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

_now = datetime.now(timezone.utc)
_tomorrow = _now + timedelta(days=1)
_next_week_start = _now + timedelta(days=(7 - _now.weekday()))
_last_month = _now - timedelta(days=30)


# ---------------------------------------------------------------------------
# Gmail mock data
# ---------------------------------------------------------------------------

MOCK_EMAILS: list[dict] = [
    {
        "email_id": "msg_tk_001",
        "thread_id": "thread_tk_001",
        "subject": "Your Turkish Airlines Booking Confirmation - TK1234",
        "sender": "reservations@turkishairlines.com",
        "to": "demo@workspace.dev",
        "recipients": "demo@workspace.dev",
        "date": (_now - timedelta(days=40)).isoformat(),
        "snippet": "Dear Passenger, your booking TK1234 from Istanbul (IST) to New York (JFK) on "
                   f"{(_now + timedelta(days=12)).strftime('%B %d, %Y')} at 10:30 AM has been confirmed. "
                   "Booking reference: XHGT7K. Total: $842.00.",
        "body_preview": "Dear Passenger, your booking TK1234 from Istanbul (IST) to New York (JFK) has been confirmed. "
                        "Booking reference: XHGT7K. Departure: 10:30 AM. Terminal: International.",
        "labels": ["INBOX", "CATEGORY_UPDATES"],
        "received_at": (_now - timedelta(days=40)).isoformat(),
    },
    {
        "email_id": "msg_acme_001",
        "thread_id": "thread_acme_001",
        "subject": "Re: Acme Corp Partnership Proposal - Next Steps",
        "sender": "jane.smith@acmecorp.com",
        "to": "demo@workspace.dev",
        "recipients": "demo@workspace.dev, bob@acmecorp.com",
        "date": (_now - timedelta(days=2)).isoformat(),
        "snippet": "Hi, thanks for sending over the revised proposal. The team reviewed it and we're aligned on the "
                   "pricing structure. Let's discuss the implementation timeline in tomorrow's meeting.",
        "body_preview": "Hi, thanks for sending over the revised proposal. The team reviewed it and we're aligned on the "
                        "pricing structure. Let's discuss the implementation timeline in tomorrow's meeting. "
                        "Also attaching our technical requirements doc for your reference.",
        "labels": ["INBOX", "IMPORTANT"],
        "received_at": (_now - timedelta(days=2)).isoformat(),
    },
    {
        "email_id": "msg_acme_002",
        "thread_id": "thread_acme_001",
        "subject": "Acme Corp Partnership Proposal - Next Steps",
        "sender": "demo@workspace.dev",
        "to": "jane.smith@acmecorp.com",
        "recipients": "jane.smith@acmecorp.com, bob@acmecorp.com",
        "date": (_now - timedelta(days=5)).isoformat(),
        "snippet": "Hi Jane, please find attached the revised proposal with updated pricing for the Q1 rollout. "
                   "Key changes include volume discounts and extended support.",
        "body_preview": "Hi Jane, please find attached the revised proposal with updated pricing for Q1.",
        "labels": ["SENT"],
        "received_at": (_now - timedelta(days=5)).isoformat(),
    },
    {
        "email_id": "msg_budget_001",
        "thread_id": "thread_budget_001",
        "subject": "Q4 Budget Review - Action Items",
        "sender": "sarah@company.com",
        "to": "demo@workspace.dev",
        "recipients": "demo@workspace.dev, finance-team@company.com",
        "date": (_now - timedelta(days=3)).isoformat(),
        "snippet": "Hi team, following up on our Q4 budget discussion. We need to finalize allocations by Friday. "
                   "Marketing is requesting an additional $50K for the product launch campaign.",
        "body_preview": "Following up on Q4 budget discussion. Finalize allocations by Friday. "
                        "Marketing requesting additional $50K.",
        "labels": ["INBOX", "IMPORTANT"],
        "received_at": (_now - timedelta(days=3)).isoformat(),
    },
    {
        "email_id": "msg_budget_002",
        "thread_id": "thread_budget_002",
        "subject": "Updated Budget Spreadsheet - Q4",
        "sender": "sarah@company.com",
        "to": "demo@workspace.dev",
        "recipients": "demo@workspace.dev",
        "date": (_now - timedelta(days=7)).isoformat(),
        "snippet": "Here's the updated Q4 budget spreadsheet with the revised projections. "
                   "Please review columns F-H for the new cost centers.",
        "body_preview": "Updated Q4 budget spreadsheet with revised projections.",
        "labels": ["INBOX"],
        "received_at": (_now - timedelta(days=7)).isoformat(),
    },
    {
        "email_id": "msg_proposal_001",
        "thread_id": "thread_proposal_001",
        "subject": "Partnership Proposal Draft v3",
        "sender": "mike@company.com",
        "to": "demo@workspace.dev",
        "recipients": "demo@workspace.dev",
        "date": (_now - timedelta(days=1)).isoformat(),
        "snippet": "Hey, I've updated the partnership proposal with the legal team's feedback. "
                   "Main changes are in section 4 (liability) and section 7 (termination clauses).",
        "body_preview": "Updated partnership proposal v3 with legal feedback. Changes in section 4 and 7.",
        "labels": ["INBOX"],
        "received_at": (_now - timedelta(days=1)).isoformat(),
    },
    {
        "email_id": "msg_vacation_001",
        "thread_id": "thread_vacation_001",
        "subject": "Re: Vacation Request Approved - March 15-22",
        "sender": "hr@company.com",
        "to": "demo@workspace.dev",
        "recipients": "demo@workspace.dev",
        "date": (_now - timedelta(days=10)).isoformat(),
        "snippet": "Your vacation request for March 15-22 has been approved. "
                   "Please ensure all handoffs are completed before your leave.",
        "body_preview": "Vacation request March 15-22 approved. Complete handoffs before leave.",
        "labels": ["INBOX"],
        "received_at": (_now - timedelta(days=10)).isoformat(),
    },
    {
        "email_id": "msg_standup_001",
        "thread_id": "thread_standup_001",
        "subject": "Daily Standup Notes - Engineering",
        "sender": "scrum-master@company.com",
        "to": "engineering@company.com",
        "recipients": "engineering@company.com",
        "date": _now.isoformat(),
        "snippet": "Standup summary: 3 PRs merged, auth service deployment scheduled for Thursday, "
                   "blocked on API gateway config.",
        "body_preview": "Standup summary: 3 PRs merged, auth service deployment Thursday.",
        "labels": ["INBOX"],
        "received_at": _now.isoformat(),
    },
]


# ---------------------------------------------------------------------------
# Google Calendar mock data
# ---------------------------------------------------------------------------

MOCK_EVENTS: list[dict] = [
    {
        "event_id": "evt_flight_001",
        "title": "Istanbul → NYC Flight (TK1234)",
        "description": "Turkish Airlines TK1234. Booking ref: XHGT7K. Depart IST 10:30 AM, Arrive JFK 3:45 PM.",
        "start_time": (_now + timedelta(days=12)).replace(hour=10, minute=30).isoformat(),
        "end_time": (_now + timedelta(days=12)).replace(hour=15, minute=45).isoformat(),
        "attendees": [],
        "location": "Istanbul Airport (IST)",
        "status": "confirmed",
    },
    {
        "event_id": "evt_acme_001",
        "title": "Client Meeting - Acme Corp Partnership",
        "description": "Discuss partnership proposal, pricing, and implementation timeline with Acme Corp team.",
        "start_time": _tomorrow.replace(hour=14, minute=0, second=0).isoformat(),
        "end_time": _tomorrow.replace(hour=15, minute=0, second=0).isoformat(),
        "attendees": ["jane.smith@acmecorp.com", "bob@acmecorp.com", "demo@workspace.dev"],
        "location": "Conference Room A / Zoom",
        "status": "confirmed",
    },
    {
        "event_id": "evt_standup_001",
        "title": "Daily Engineering Standup",
        "description": "Daily sync for the engineering team.",
        "start_time": (_next_week_start).replace(hour=9, minute=30, second=0).isoformat(),
        "end_time": (_next_week_start).replace(hour=9, minute=45, second=0).isoformat(),
        "attendees": ["demo@workspace.dev", "john@company.com", "alice@company.com"],
        "location": "Zoom",
        "status": "confirmed",
    },
    {
        "event_id": "evt_budget_001",
        "title": "Q4 Budget Review",
        "description": "Final review of Q4 budget allocations. Bring updated spreadsheet.",
        "start_time": _tomorrow.replace(hour=10, minute=0, second=0).isoformat(),
        "end_time": _tomorrow.replace(hour=11, minute=0, second=0).isoformat(),
        "attendees": ["sarah@company.com", "demo@workspace.dev", "cfo@company.com"],
        "location": "Board Room",
        "status": "confirmed",
    },
    {
        "event_id": "evt_john_001",
        "title": "1:1 with John - Performance Review",
        "description": "Quarterly performance check-in with John.",
        "start_time": (_next_week_start + timedelta(days=1)).replace(hour=11, minute=0, second=0).isoformat(),
        "end_time": (_next_week_start + timedelta(days=1)).replace(hour=11, minute=30, second=0).isoformat(),
        "attendees": ["john@company.com", "demo@workspace.dev"],
        "location": "Office",
        "status": "confirmed",
    },
    {
        "event_id": "evt_ooo_001",
        "title": "Out of Office - Vacation",
        "description": "On vacation March 15-22. All meetings should be rescheduled.",
        "start_time": "2026-03-15T00:00:00+00:00",
        "end_time": "2026-03-22T23:59:59+00:00",
        "attendees": ["demo@workspace.dev"],
        "location": "",
        "status": "confirmed",
    },
]


# ---------------------------------------------------------------------------
# Google Drive mock data
# ---------------------------------------------------------------------------

MOCK_FILES: list[dict] = [
    {
        "file_id": "file_q4report_001",
        "name": "Q4 Financial Report 2025.pdf",
        "mime_type": "application/pdf",
        "modified_at": (_now - timedelta(days=5)).isoformat(),
        "description": "Quarterly financial report with revenue, expenses, and profit breakdown.",
        "content_preview": "Q4 2025 Financial Report. Revenue: $2.4M (+12% QoQ). Operating expenses: $1.8M. "
                           "Net profit: $600K. Key highlights: SaaS ARR crossed $10M.",
        "web_link": "https://docs.google.com/document/d/q4report",
        "owners": ["cfo@company.com"],
    },
    {
        "file_id": "file_acme_001",
        "name": "Acme Corp Partnership Proposal v3.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "modified_at": (_now - timedelta(days=1)).isoformat(),
        "description": "Partnership proposal for Acme Corp including pricing, SLA, and implementation plan.",
        "content_preview": "Acme Corp Partnership Proposal. Scope: Enterprise license for 500 seats. "
                           "Pricing: $45/seat/month with volume discount. Implementation: 8-week rollout.",
        "web_link": "https://docs.google.com/document/d/acme_proposal",
        "owners": ["demo@workspace.dev"],
    },
    {
        "file_id": "file_ooo_001",
        "name": "Out of Office Schedule 2026.xlsx",
        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "modified_at": (_now - timedelta(days=14)).isoformat(),
        "description": "Team OOO schedule for 2026. Tracks planned vacations and holidays.",
        "content_preview": "OOO Schedule 2026. Demo User: March 15-22 (vacation), May 1 (holiday). "
                           "John: April 5-9 (conference). Sarah: Feb 28 (personal day).",
        "web_link": "https://docs.google.com/spreadsheets/d/ooo_schedule",
        "owners": ["hr@company.com"],
    },
    {
        "file_id": "file_budget_001",
        "name": "Q4 Budget Allocation.xlsx",
        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "modified_at": (_now - timedelta(days=7)).isoformat(),
        "description": "Q4 budget allocation spreadsheet with department breakdowns.",
        "content_preview": "Q4 Budget Allocation. Engineering: $500K. Marketing: $300K (+$50K requested). "
                           "Sales: $200K. Operations: $150K. Total: $1.2M.",
        "web_link": "https://docs.google.com/spreadsheets/d/budget_q4",
        "owners": ["sarah@company.com"],
    },
    {
        "file_id": "file_notes_001",
        "name": "Acme Corp Meeting Notes - Jan 2026.gdoc",
        "mime_type": "application/vnd.google-apps.document",
        "modified_at": (_now - timedelta(days=20)).isoformat(),
        "description": "Notes from previous meetings with Acme Corp.",
        "content_preview": "Meeting Notes Jan 15: Discussed initial partnership scope. Acme wants integration "
                           "with their CRM. Action items: send pricing proposal, schedule technical deep-dive.",
        "web_link": "https://docs.google.com/document/d/acme_notes",
        "owners": ["demo@workspace.dev"],
    },
]


# ---------------------------------------------------------------------------
# Mock API response builders (match Google API response shapes)
# ---------------------------------------------------------------------------

def mock_gmail_messages_list(query: str = "") -> dict:
    """Simulate GET /gmail/v1/users/me/messages response."""
    q_lower = query.lower()
    matches = []
    for e in MOCK_EMAILS:
        searchable = f"{e['subject']} {e['sender']} {e['body_preview']}".lower()
        if not q_lower or q_lower in searchable:
            matches.append({"id": e["email_id"], "threadId": e["thread_id"]})
    return {"messages": matches, "resultSizeEstimate": len(matches)}


def mock_gmail_message_get(message_id: str) -> dict:
    """Simulate GET /gmail/v1/users/me/messages/{id} response."""
    for e in MOCK_EMAILS:
        if e["email_id"] == message_id:
            return {
                "id": e["email_id"],
                "threadId": e["thread_id"],
                "snippet": e["snippet"],
                "labelIds": e["labels"],
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": e["subject"]},
                        {"name": "From", "value": e["sender"]},
                        {"name": "To", "value": e["to"]},
                        {"name": "Date", "value": e["date"]},
                    ]
                },
            }
    return {"id": message_id, "snippet": "", "payload": {"headers": []}}


def mock_gmail_draft_create(**kwargs) -> dict:
    return {"id": "draft_demo_001", "message": {"id": "msg_draft_001"}}


def mock_gmail_send(**kwargs) -> dict:
    return {"id": "msg_sent_001", "threadId": "thread_sent_001"}


def mock_gcal_events_list(query: str = "", time_min: str = "", time_max: str = "") -> dict:
    """Simulate GET /calendar/v3/calendars/primary/events response."""
    q_lower = query.lower()
    items = []
    for ev in MOCK_EVENTS:
        searchable = f"{ev['title']} {ev['description']}".lower()
        if not q_lower or q_lower in searchable:
            items.append({
                "id": ev["event_id"],
                "summary": ev["title"],
                "description": ev["description"],
                "start": {"dateTime": ev["start_time"]},
                "end": {"dateTime": ev["end_time"]},
                "attendees": [{"email": a} for a in ev["attendees"]],
                "location": ev["location"],
                "status": ev["status"],
            })
    return {"items": items}


def mock_gcal_event_get(event_id: str) -> dict:
    for ev in MOCK_EVENTS:
        if ev["event_id"] == event_id:
            return {
                "id": ev["event_id"],
                "summary": ev["title"],
                "description": ev["description"],
                "start": {"dateTime": ev["start_time"]},
                "end": {"dateTime": ev["end_time"]},
                "attendees": [{"email": a} for a in ev["attendees"]],
                "location": ev["location"],
                "status": ev["status"],
            }
    return {"id": event_id, "summary": "Unknown Event"}


def mock_drive_files_list(query: str = "") -> dict:
    """Simulate GET /drive/v3/files response."""
    q_lower = query.lower()
    files = []
    for f in MOCK_FILES:
        searchable = f"{f['name']} {f['description']} {f['content_preview']}".lower()
        if not q_lower or q_lower in searchable:
            files.append({
                "id": f["file_id"],
                "name": f["name"],
                "mimeType": f["mime_type"],
                "modifiedTime": f["modified_at"],
                "description": f["description"],
            })
    return {"files": files}


def mock_drive_file_get(file_id: str) -> dict:
    for f in MOCK_FILES:
        if f["file_id"] == file_id:
            return {
                "id": f["file_id"],
                "name": f["name"],
                "mimeType": f["mime_type"],
                "modifiedTime": f["modified_at"],
                "description": f["description"],
                "webViewLink": f.get("web_link", ""),
                "owners": [{"emailAddress": o} for o in f.get("owners", [])],
            }
    return {"id": file_id, "name": "Unknown File"}


def route_mock_request(method: str, url: str, params: dict | None = None, json_body: dict | None = None) -> dict:
    """Route a mock request to the appropriate handler based on URL pattern."""
    params = params or {}

    # Gmail
    if "/gmail/" in url:
        if url.endswith("/messages") and method == "GET":
            return mock_gmail_messages_list(params.get("q", ""))
        if "/messages/" in url and method == "GET":
            msg_id = url.split("/messages/")[-1].split("?")[0]
            return mock_gmail_message_get(msg_id)
        if url.endswith("/drafts") and method == "POST":
            return mock_gmail_draft_create()
        if url.endswith("/send") and method == "POST":
            return mock_gmail_send()
        if "/modify" in url:
            return {"id": "modified"}

    # Calendar
    if "/calendar/" in url:
        if url.endswith("/events") and method == "GET":
            return mock_gcal_events_list(params.get("q", ""), params.get("timeMin", ""), params.get("timeMax", ""))
        if "/events/" in url and method == "GET":
            event_id = url.split("/events/")[-1]
            return mock_gcal_event_get(event_id)
        if url.endswith("/events") and method == "POST":
            return {"id": "evt_new_001", "summary": json_body.get("summary", "")}
        if "/events/" in url and method in ("PATCH", "PUT"):
            event_id = url.split("/events/")[-1]
            return {"id": event_id, "summary": (json_body or {}).get("summary", "Updated")}

    # Drive
    if "/drive/" in url:
        if url.endswith("/files") and method == "GET":
            q = params.get("q", "")
            search_term = ""
            if "fullText contains" in q:
                search_term = q.split("'")[1] if "'" in q else ""
            return mock_drive_files_list(search_term)
        if "/files/" in url and "/permissions" not in url and method == "GET":
            file_id = url.split("/files/")[-1].split("?")[0]
            return mock_drive_file_get(file_id)
        if "/permissions" in url:
            return {"id": "perm_001"}
        if method == "POST":
            return {"id": "file_new_001", "name": (json_body or {}).get("name", "")}

    return {"status": "ok"}
