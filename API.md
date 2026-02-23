# API Reference

Base URL: `http://localhost:8000`

OpenAPI spec available at: `http://localhost:8000/docs`

---

## Authentication

### Start OAuth Flow

```
GET /api/v1/auth/google
```

Redirects to Google OAuth consent screen. After authorization, Google redirects back to the callback URL.

**Response:** `307 Redirect` to Google OAuth

### OAuth Callback

```
GET /api/v1/auth/google/callback?code={authorization_code}
```

Exchanges the authorization code for access/refresh tokens and creates or updates the user.

**Response:**
```json
{
  "user_id": "12345678-1234-1234-1234-123456789abc",
  "email": "user@example.com",
  "message": "Authentication successful"
}
```

---

## Query Processing

### Process Natural Language Query

```
POST /api/v1/query
```

**Headers:**
| Header | Type | Required | Description |
|--------|------|----------|-------------|
| `X-User-Id` | UUID | Yes | Authenticated user ID |

**Request Body:**
```json
{
  "query": "Cancel my Turkish Airlines flight",
  "conversation_id": "optional-uuid-for-context"
}
```

**Response:**
```json
{
  "conversation_id": "uuid",
  "query": "Cancel my Turkish Airlines flight",
  "response": "I found your Turkish Airlines booking (TK1234) in an email from Oct 15.\n✓ Calendar event \"Istanbul → NYC Flight\" on Nov 5 at 10:30 AM\n✓ Drafted cancellation email to support@turkishairlines.com\nWould you like me to send it?",
  "actions_taken": [
    {
      "service": "gmail",
      "action": "search_emails",
      "status": "success",
      "detail": "3 result(s)"
    },
    {
      "service": "gcal",
      "action": "search_events",
      "status": "success",
      "detail": "Event: Istanbul → NYC Flight"
    },
    {
      "service": "gmail",
      "action": "draft_email",
      "status": "success",
      "detail": "Email: Re: Booking Confirmation"
    }
  ],
  "created_at": "2026-02-23T12:00:00Z"
}
```

**Error Responses:**
| Status | Description |
|--------|-------------|
| 401 | User has no valid Google tokens |
| 404 | User not found |
| 422 | Invalid request body |
| 429 | Rate limit exceeded (100 queries/hour) |

---

## Sync

### Trigger Manual Sync

```
POST /api/v1/sync/trigger
```

**Headers:**
| Header | Type | Required | Description |
|--------|------|----------|-------------|
| `X-User-Id` | UUID | Yes | Authenticated user ID |

**Response:**
```json
{
  "message": "Sync triggered for all services",
  "services": ["gmail", "gcal", "drive"]
}
```

### Get Sync Status

```
GET /api/v1/sync/status
```

**Headers:**
| Header | Type | Required | Description |
|--------|------|----------|-------------|
| `X-User-Id` | UUID | Yes | Authenticated user ID |

**Response:**
```json
[
  {
    "service": "gmail",
    "last_sync_at": "2026-02-23T11:45:00Z",
    "status": "completed"
  },
  {
    "service": "gcal",
    "last_sync_at": "2026-02-23T11:45:00Z",
    "status": "completed"
  },
  {
    "service": "drive",
    "last_sync_at": null,
    "status": "never_synced"
  }
]
```

---

## Health

### Health Check

```
GET /health
```

**Response:**
```json
{
  "status": "ok"
}
```

---

## Query Examples

### Single-Service Queries

```bash
# Calendar search
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-User-Id: your-user-id" \
  -d '{"query": "What'\''s on my calendar next week?"}'

# Email search
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-User-Id: your-user-id" \
  -d '{"query": "Find emails from sarah@company.com about the budget"}'

# Drive search
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-User-Id: your-user-id" \
  -d '{"query": "Show me PDFs in Drive from last month"}'
```

### Multi-Service Queries

```bash
# Flight cancellation (Gmail + Calendar)
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-User-Id: your-user-id" \
  -d '{"query": "Cancel my Turkish Airlines flight"}'

# Meeting preparation (Calendar + Gmail + Drive)
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-User-Id: your-user-id" \
  -d '{"query": "Prepare for tomorrow'\''s client meeting with Acme Corp"}'
```

### Ambiguous Queries

```bash
# Returns clarification request
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-User-Id: your-user-id" \
  -d '{"query": "Move the meeting with John"}'
```

---

## Rate Limits

| Limit | Value |
|-------|-------|
| Queries per user per hour | 100 |
| Request body max size | 2000 characters |
| Google API retry attempts | 3 (with exponential backoff) |
