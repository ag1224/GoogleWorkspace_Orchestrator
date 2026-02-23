# Google Workspace Orchestrator

An intelligent orchestration layer that processes natural language queries against Gmail, Google Calendar, and Google Drive. Built with FastAPI, PostgreSQL (pgvector), Redis, Celery, and OpenAI.

## Architecture

```
User Query
    │
    ▼
Intent Classifier (LLM + few-shot prompting)
    │
    ▼
Query Planner (DAG with topological sort)
    │
    ▼
Service Orchestrator (parallel async execution)
    ├── Gmail Agent (search, read, send, draft)
    ├── GCal Agent (search, create, update, delete)
    └── Drive Agent (search, read, share)
    │
    ▼
Embedding & Search (pgvector + hybrid search)
    │
    ▼
Response Synthesizer (natural language output)
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Google Cloud project with Gmail, Calendar, and Drive APIs enabled
- OpenAI API key

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 2. Start infrastructure

```bash
docker compose up -d db redis
```

### 3. Run migrations

```bash
uv run alembic upgrade head
```

### 4. Start the app

```bash
uv run uvicorn app.main:app --reload
```

### 5. Start Celery workers (separate terminal)

```bash
uv run celery -A app.workers.celery_app worker --loglevel=info
```

### Or use Docker Compose for everything

```bash
docker compose up --build
```

## Usage

### 1. Authenticate

Visit `http://localhost:8000/api/v1/auth/google` to start the OAuth flow.

### 2. Query

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-User-Id: YOUR_USER_ID" \
  -d '{"query": "What'\''s on my calendar next week?"}'
```

### 3. Sync data

```bash
curl -X POST http://localhost:8000/api/v1/sync/trigger \
  -H "X-User-Id: YOUR_USER_ID"
```

## Project Structure

```
app/
├── main.py                     # FastAPI app + lifespan
├── config.py                   # Pydantic Settings
├── models/                     # SQLAlchemy ORM
│   ├── user.py
│   ├── conversation.py
│   └── cache.py                # gmail/gcal/drive cache + sync_status
├── schemas/                    # Pydantic request/response
│   └── query.py
├── api/v1/                     # API routes
│   ├── auth.py                 # OAuth flow
│   ├── query.py                # POST /query
│   └── sync.py                 # Sync triggers + status
├── core/                       # Orchestration engine
│   ├── intent_classifier.py    # LLM-based intent parsing
│   ├── query_planner.py        # DAG builder + topological sort
│   ├── orchestrator.py         # Parallel execution engine
│   └── response_synthesizer.py # Natural language aggregation
├── agents/                     # Google service agents
│   ├── base.py                 # Abstract agent with retry
│   ├── gmail_agent.py
│   ├── gcal_agent.py
│   └── drive_agent.py
├── services/                   # Shared services
│   ├── google_auth.py          # OAuth token management
│   ├── embedding.py            # OpenAI embeddings + batch
│   └── vector_search.py        # pgvector hybrid search
├── cache/
│   └── redis_client.py         # Redis caching layer
├── workers/
│   ├── celery_app.py           # Celery config + beat schedule
│   └── tasks.py                # Background sync tasks
└── db/
    ├── database.py             # Async SQLAlchemy engine
    └── migrations/             # Alembic migrations
```

## Key Design Decisions

- **No LangChain/LlamaIndex** — orchestration built from scratch with asyncio + custom DAG
- **pgvector** — IVFFlat indexes with cosine similarity for semantic search
- **Hybrid search** — vector similarity combined with metadata SQL filters (date, sender, type)
- **Temporal decay** — recent items weighted higher: `score * 1/log(days_ago + 2)`
- **Graceful degradation** — partial results returned when individual services fail
- **Encrypted tokens** — Fernet symmetric encryption for stored OAuth tokens

## Testing

```bash
uv run pytest tests/ -v
```

## Documentation

- [API.md](API.md) — Full API reference with curl examples
- [DESIGN.md](DESIGN.md) — Scaling strategy for 1M users
- [sample_queries.json](sample_queries.json) — 13 test queries with expected outputs

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/query` | Process natural language query |
| GET | `/api/v1/auth/google` | Start OAuth flow |
| GET | `/api/v1/auth/google/callback` | OAuth callback |
| POST | `/api/v1/sync/trigger` | Manual sync |
| GET | `/api/v1/sync/status` | Sync timestamps |
| GET | `/health` | Health check |
