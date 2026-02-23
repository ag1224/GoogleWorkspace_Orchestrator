# Design Document — Scaling to 1M Users

## Architecture Overview

```
                    ┌─────────────┐
                    │   CDN/LB    │
                    │ (CloudFlare)│
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ FastAPI  │ │ FastAPI  │ │ FastAPI  │
        │ Server 1 │ │ Server 2 │ │ Server N │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │             │             │
    ┌────────┴─────────────┴─────────────┴────────┐
    │                Redis Cluster                 │
    │  (cache, rate limits, session, Celery broker)│
    └────────┬─────────────────────────────────────┘
             │
    ┌────────┴─────────────────────────────────────┐
    │           PostgreSQL (Citus/sharded)          │
    │   pgvector for embeddings, JSONB for metadata │
    └────────┬─────────────────────────────────────┘
             │
    ┌────────┴──────────┐
    │   Celery Workers  │
    │   (auto-scaling)  │
    └───────────────────┘
```

## Sharding Strategy

### User-based Partitioning

All tables are partitioned by `user_id` using hash partitioning:

```sql
CREATE TABLE gmail_cache (
    ...
) PARTITION BY HASH (user_id);

CREATE TABLE gmail_cache_p0 PARTITION OF gmail_cache FOR VALUES WITH (modulus 16, remainder 0);
CREATE TABLE gmail_cache_p1 PARTITION OF gmail_cache FOR VALUES WITH (modulus 16, remainder 1);
-- ... through p15
```

Benefits:
- Queries always filter by user_id → single partition scan
- Even distribution across partitions
- Each partition gets its own IVFFlat index
- Easy to add more partitions as data grows

### Vector Index Tuning

- IVFFlat with `lists = sqrt(n)` where n = rows per partition
- For 1M users × 200 emails avg = 200M embeddings → ~16 partitions × 12.5M each
- `lists = 3500` per partition, `probes = 10` at query time
- Alternative: HNSW index for higher recall at cost of memory

## Caching Architecture

### Three-Tier Cache

| Tier | Store | TTL | Content |
|------|-------|-----|---------|
| L1 | In-process (LRU) | 60s | Hot intent classifications |
| L2 | Redis Cluster | 5min-1hr | Embeddings, intents, conversation context |
| L3 | PostgreSQL | Persistent | Full cache tables with vector indexes |

### Cache Key Design

```
emb:{sha256(text)[:32]}          → embedding vector (1hr TTL)
intent:{sha256(query)[:32]}      → classified intent JSON (5min TTL)
ctx:{user_id}                    → last 5 queries list (30min TTL)
rl:{user_id}                     → rate limit counter (1hr window)
sync:{user_id}:{service}         → last sync token (no TTL)
```

### Cache Hit Rate Target: >80%

- Embedding cache: high hit rate because same emails/events queried repeatedly
- Intent cache: moderate hit rate, similar queries map to same intent
- Conversation context: per-session, always fresh

## Rate Limiting

### Per-User Limits
- 100 queries/hour (sliding window via Redis INCR + EXPIRE)
- Burst: 10 queries/minute

### Google API Quota Management
- Default: 250 quota units/second/user
- Gmail read: 5 units, write: 50 units
- Calendar read: 1 unit, write: 3 units
- Drive read: 3 units, write: 5 units

Strategy:
1. Token bucket per user per service in Redis
2. If approaching limit, queue requests in Celery
3. Exponential backoff on 429 responses (1s → 2s → 4s → 8s)
4. Circuit breaker: after 5 consecutive failures, disable service for 30s

## Async Processing

### Celery Task Queue

```
High Priority Queue (query processing):
  - Intent classification
  - Service orchestration
  - Response synthesis

Low Priority Queue (background sync):
  - Periodic email/calendar/drive sync
  - Embedding generation for new content
  - Cache warming
```

### Worker Scaling

| Load Level | API Servers | Celery Workers | Redis | PostgreSQL |
|-----------|-------------|---------------|-------|------------|
| 10K users | 2 | 4 | 1 primary + 1 replica | 1 primary + 1 replica |
| 100K users | 4 | 16 | 3-node cluster | Primary + 2 replicas |
| 1M users | 8-12 | 32-64 | 6-node cluster | Citus (4 workers) |

## Multi-Region Deployment

```
US-East:  API + Workers + PostgreSQL primary + Redis primary
US-West:  API + Workers + PostgreSQL replica + Redis replica
EU-West:  API + Workers + PostgreSQL replica + Redis replica
APAC:     API + Workers + PostgreSQL replica + Redis replica
```

- Geo-routing via CloudFlare/Route53
- Write operations routed to primary region
- Read replicas serve search queries with <50ms added latency
- User data stays in region (GDPR compliance for EU)

## Embedding Freshness

### Incremental Sync Pipeline

```
Every 15 min per user:
1. Check Google API sync tokens for changes
2. Fetch only new/modified items (incremental)
3. Generate embeddings in batch (up to 2048 per API call)
4. Upsert into pgvector cache tables
5. Update sync_status table
```

### Freshness Guarantees
- New emails indexed within 15 minutes
- Manual sync endpoint for immediate indexing
- Webhook support (Gmail push notifications) for near-real-time

## Monitoring & Observability

### Key Metrics

| Metric | Target | Alert Threshold |
|--------|--------|----------------|
| P50 latency | <500ms | >1s |
| P99 latency | <2s | >5s |
| Cache hit rate | >80% | <60% |
| Google API error rate | <0.1% | >1% |
| Embedding freshness | <15min | >30min |
| Queue depth | <100 | >1000 |

### Instrumentation
- OpenTelemetry for distributed tracing
- Prometheus metrics exported from FastAPI
- Structured JSON logging with correlation IDs
- PgBouncer connection pooling metrics

## Security

### Token Storage
- OAuth tokens encrypted at rest with Fernet (AES-128-CBC)
- Encryption key from environment variable, rotatable
- Token refresh handled transparently before API calls

### Multi-Tenant Isolation
- All queries filter by `user_id` — no cross-tenant data access
- Row-level security (RLS) as defense-in-depth:
  ```sql
  ALTER TABLE gmail_cache ENABLE ROW LEVEL SECURITY;
  CREATE POLICY user_isolation ON gmail_cache USING (user_id = current_setting('app.current_user_id')::uuid);
  ```

### Audit Logging
- All queries logged in `conversations` table
- All write operations (send email, create event) logged with before/after state
- 90-day retention, archived to object storage

## Cost Estimation (1M Users)

| Component | Monthly Cost |
|-----------|-------------|
| API Servers (8× c5.xlarge) | $1,200 |
| Celery Workers (16× c5.large) | $1,200 |
| PostgreSQL (Citus, 4 workers) | $2,000 |
| Redis Cluster (6 nodes) | $900 |
| OpenAI Embeddings (50M calls/mo) | $1,000 |
| OpenAI GPT-4o-mini (10M calls/mo) | $3,000 |
| **Total** | **~$9,300/mo** |
