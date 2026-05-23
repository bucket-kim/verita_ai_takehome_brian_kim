# Metered API Billing System - Design Document

## Data Model & Index Strategy

### Core Schema

**Customer** (UUID) → ApiKey (SHA256 hashed), UsageEvent, Invoice, Credit
**UsageEvent** (immutable) → request_id UNIQUE (idempotency), event_timestamp, units
**UsageWindow** (derived) → UNIQUE(customer_id, window_start), total_units (recomputable from events)
**Invoice** (immutable after generation) → period, status, total_cents (derived from line items)
**AuditLog** (programmatically immutable) → save/delete raise PermissionError

### Index Justification with Query Patterns

**UsageEvent(request_id) UNIQUE**
- Query: `bulk_create(events, ignore_conflicts=True)` on every POST /v1/events
- Frequency: 200/sec sustained, 2,000/sec peak
- Without: Duplicate events counted multiple times → billing errors
- With: Database rejects duplicates atomically, O(1) lookup <1ms

**UsageEvent(customer_id, event_timestamp)**
- Query: `GROUP BY customer, TruncHour(event_timestamp)` in aggregator every 5min
- Without index: Full scan 100M rows = 300+ sec (exceeds 5min interval)
- With index: Index scan + aggregate = 15 sec
- Critical: Without this, aggregator falls behind, invoices show $0

**UsageEvent(customer_id, event_timestamp) WHERE finalized=false (Partial)**
- At production: 99%+ events finalized, partial index 100× smaller
- Index size: ~100KB (1M unfinalized) vs 10GB (1B total)
- Performance: Sub-second even at 1B total events
- Add: Phase 1 (Week 1)

**UsageWindow(customer_id, window_start) UNIQUE**
- Query: `update_or_create(customer, window_start, ...)` every 5min
- Why UNIQUE: Prevents duplicate hourly buckets if aggregator runs twice
- Without: Multiple rows for same hour → invoice counts usage twice

**ApiKey(key_hash)**
- Query: Authentication on every /v1 request (1,000+ req/sec at scale)
- Without: O(N) scan (>100ms for 10k keys)
- With: O(1) hash lookup (<1ms)

**Invoice(customer_id, status)**
- Query: Ops console `filter(customer=X, status='issued')`
- Without: Full scan (>1s for 1000+ invoices)
- With: Direct seek (<10ms)

### Scaling Indexes

**10× (5B events/month, 2,000/sec):** Partial index on finalized flag → aggregator stays <10sec
**100× (50B events/month, 20k/sec):** Partition by month (2B rows/partition), archive 90+ days to S3

## Idempotency & Concurrency

**Event ingestion:** `bulk_create(ignore_conflicts=True)` + UNIQUE(request_id) → concurrent threads can't create duplicates
**Webhook processing:** `get_or_create(external_id=...)` → replays return "already_processed"
**Credit issuance:** `select_for_update()` on Customer row → concurrent ops can't double-credit
**Aggregator:** `update_or_create()` with UNIQUE(customer, window_start) → running twice produces same result

**Concurrency test example:**
```python
# 10 threads POST same request_id → verify 1 event created, 1 "created" + 9 "duplicate"
with ThreadPoolExecutor(10) as executor:
    results = [executor.submit(post_event, same_request_id).result() for _ in range(10)]
assert UsageEvent.objects.filter(request_id=same_request_id).count() == 1
```

## Aggregation Pipeline & State Management

**Flow:** UsageEvent (raw) → [aggregator 5min] → UsageWindow (hourly) → [generator monthly] → Invoice

**State categories:**
- Primary (immutable): UsageEvent, Invoice period/line items, AuditLog
- Derived (recomputable): UsageWindow from events, Invoice.total from line items
- Mutable: UsageEvent.finalized flag, Invoice.status (issued→paid)

**Recovery:** If UsageWindow corrupted → rebuild via `SELECT SUM(units) FROM events WHERE timestamp IN [window_start, window_end) GROUP BY customer`

**Late events:** Arrive after invoice generated → add adjustment line item in next invoice (preserves invoice immutability for accounting/legal)

### Reconciliation

**Query:** Compare window totals to event sums
```python
event_sum = UsageEvent.objects.filter(timestamp IN window_hour).aggregate(Sum('units'))
if event_sum != window.total_units:
    drift_pct = abs(diff) / event_sum
```

**Alerting thresholds:**
- >0% drift: Log
- >1% drift: Alert ops
- >5% drift: Critical escalation
- >10% drift: Halt invoice generation

**Schedule:** Nightly for previous day, pre-invoice for full month (11pm before midnight generation)

## Failure Modes at Scale

### Target: 5k customers, 500M events/month (200/sec sustained, 2k/sec peak)

**Bottleneck #1: Aggregation at Day 6**
- When: 100M events accumulated (100M / 16.67M/day = 6 days)
- Symptom: Aggregator query >5min (exceeds job interval), JobLock prevents concurrent runs, backlog builds
- Why: Full table scan without partial index
- Fix: `CREATE INDEX idx_unfinalized ON usage_event(customer_id, event_timestamp) WHERE finalized=false` + batch finalization after aggregation
- Cost: 6 hours dev
- Result: Scales to 500M/month indefinitely

**Bottleneck #2: Invoice Generation at Month 1**
- When: 5k customers (5k × 1sec = 83min), synchronous iteration
- Symptom: Risks timeout/crash mid-run, no automatic resume
- Fix: Celery task queue with per-customer tasks + read replicas
- Cost: 4 days dev + $200/month (Redis + replicas)
- Result: Scales to 100k customers

**Bottleneck #3: Database at Month 2**
- When: 1B events accumulated
- Symptom: All queries extremely slow despite indexes
- Fix: Partition by month (`PARTITION BY RANGE(event_timestamp)`), archive 90+ days
- Cost: 3 days dev + $100/month storage
- Result: Scales for years

**What breaks FIRST:** Aggregation at Day 6 (violates contractual accuracy).

## Threat Model

### Hostile Customer

**Attack 1: Cross-tenant access**
- Vector: `GET /v1/invoices/{other_customer_invoice_uuid}`
- Defense: `TenantScopedAPIView` base class → `get_object_or_404(Invoice, id=X, customer=self.customer)` SQL: `WHERE id=X AND customer_id=authenticated_customer`
- Result: 404 (not 403, prevents info leak)
- Residual: None

**Attack 2: Event replay**
- Vector: Submit same request_id 1000×
- Defense: UNIQUE(request_id), database rejects duplicates
- Result: Only first counted
- Residual: None (database-level)

**Attack 3: API key brute force**
- Vector: Try random keys
- Defense: SHA256 keyspace (2^256), would take 10^63 years at 1M attempts/sec
- Residual: Rate limiting missing (Phase 1: 10 fails/min → 15min ban)

### Hostile Internal User

**Attack 1: Fraudulent credit without audit**
- Vector: Direct SQL `INSERT INTO credits` + `DELETE FROM audit_logs`
- Defense: API creates credit + audit in same `transaction.atomic()`, AuditLog.delete() raises PermissionError, database REVOKE DELETE
- Result: All credits logged, cannot delete via ORM or SQL
- Residual: DBA with raw access (mitigation: pg_audit)

**Attack 2: Invoice tampering**
- Vector: Modify invoice.total_cents directly
- Defense: total_cents derived (recalculated from line items), overrides require reason + AuditLog with before/after
- Result: Changes visible, original preserved, audited
- Residual: Ops can legitimately adjust (feature, not bug)

### Compromised Webhook

**Attack 1: Replay legitimate webhook**
- Vector: Capture valid webhook, replay 100×
- Defense: `get_or_create(external_id=...)` + UNIQUE constraint
- Result: First marks paid, next 99 return "already_processed"
- Residual: None (concurrent-safe)

**Attack 2: Forge signature**
- Vector: Guess HMAC without secret
- Defense: HMAC-SHA256 keyspace 2^256, `hmac.compare_digest()` constant-time
- Result: 401 Unauthorized, no invoice modification
- Residual: If WEBHOOK_SECRET leaked (mitigation: immediate rotation, never log signatures)

**Attack 3: Modify payload**
- Vector: Change invoice_id after signature
- Defense: HMAC covers entire body, modified body ≠ signature
- Result: 401 Unauthorized
- Residual: None (integrity protected)

## Trade-offs

### 1. Hourly Windows vs Real-Time Redis
**Chose:** Hourly pre-aggregation (5min job)
**Rejected:** Real-time Redis counters
**Why:** Predictable cost (720 windows vs 1M events), no Redis failure mode, late events recompute affected window
**Cost:** 5min lag, late event adjustments
**Revisit:** At 10k/sec sustained need streaming (Flink)

### 2. Cursor vs Offset Pagination
**Chose:** Cursor (`base64(timestamp|id)`)
**Rejected:** Offset (LIMIT N OFFSET M)
**Why:** Stable under concurrent writes (100 new events between pages don't skip rows), billing reconciliation needs correctness
**Cost:** Can't jump to pages, no total count
**Never revisit:** Correctness requirement for billing data

### 3. Adjustment vs Recompute Late Events
**Chose:** Adjustment line items in next invoice
**Rejected:** Recompute past invoices
**Why:** Invoice immutability (accounting/legal), simpler auditing
**Cost:** Billing lag (pay next month)
**Acceptable:** <1% of events are late

### 4. UUIDs vs Integer IDs
**Chose:** UUIDs for Customer, Invoice, Event
**Rejected:** Sequential integers
**Why:** Prevents enumeration attacks, no "customer has 73 invoices" leak
**Cost:** 16 bytes vs 4 bytes, slightly slower joins
**Worth it:** Security > performance for PII

### 5. Programmatic vs Database Immutability for AuditLog
**Chose:** Programmatic (PermissionError on save/delete)
**Rejected:** Database triggers/permissions
**Why:** Simpler testing, explicit in code, same tamper evidence
**Cost:** Not enforced if direct SQL
**Acceptable:** Ops shouldn't bypass ORM, database-level via REVOKE DELETE

## What We Didn't Build

**Not built (intentional):**
- Rate limiting per API key (not needed at 5k customers, build at abuse observed)
- Read replicas (single DB handles current load, add at >10k events/sec sustained)
- Event timestamp validation (trust client for MVP, reject >1hr drift in production)
- Streaming aggregation (batch wins at 200/sec, need Flink at >10k/sec)

**Would build next (priority order):**
1. **Partial index + finalization** - Prevents Day 6 bottleneck, 6hr dev, $0 cost (Phase 1 REQUIRED)
2. **Table partitioning** - Scales for years, 3d dev, $100/mo storage (Phase 2 REQUIRED)
3. **Celery + read replicas** - Fault-tolerant invoicing, 4d dev, $200/mo (Phase 3 REQUIRED)
4. **Rate limiting** - Prevents abuse, 2d dev, $0 cost (security hardening)
5. **Monitoring/alerting** - Ops visibility, 3d dev, $300/mo (production hardening)

## Testing Strategy

**Concurrency tests (ThreadPoolExecutor):**
- 10 threads same request_id → 1 event created
- 5 threads same idempotency key → 1 credit issued
- Aggregator runs twice → window total unchanged
- 10 webhooks concurrent → invoice marked paid once

**Integration tests:**
- Tiered pricing: 150k units → verify $11,500 (millicents arithmetic)
- Late event adjustment in next invoice
- Cross-tenant isolation (query other customer → 404)
- Audit log immutability (save/delete → PermissionError)

**Don't test:** Trivial getters, Django ORM basics, framework functionality

## Technology Choices

**Django REST Framework** (vs FastAPI): Mature, batteries included (auth, pagination)
**PostgreSQL** (vs MySQL): ACID, rich constraints
**APScheduler** (vs Celery): Simple for current scale, need Celery at 10×
**UUIDs** (vs integers): Security > performance for tenant isolation
**Cursor pagination** (vs offset): Correctness > convenience for billing

## Migration Path

### Phase 1 (Week 1, 6hr dev, $0) - REQUIRED
- Partial index `WHERE finalized=false`
- Batch finalization after aggregation
- Survives Month 1

### Phase 2 (Weeks 2-4, 3d dev, $100/mo) - REQUIRED
- Partition by month
- Archive 90+ days to S3
- Scales for years

### Phase 3 (Month 2, 4d dev, $200/mo) - REQUIRED
- Celery for invoice generation
- Read replicas for /v1 API
- Handles 10k+ customers

### Phase 4 (Month 6+, 1w dev, $500/mo) - OPTIONAL
- Modulo sharding (10 workers)
- Handles 2k/sec sustained

**Total investment:** 2 weeks dev over 2 months + $300-500/mo

## Conclusion

**Production readiness:** ❌ Current breaks Day 6 → ✅ After Phase 1-3 production-ready

**Key strengths:** Database constraints prevent bugs, immutability prevents tampering, idempotency prevents duplicates, tenant isolation prevents leaks, clear evolutionary path

**What breaks first:** Aggregation at Day 6 (100M events, query >5min, JobLock prevents concurrent runs, invoices show $0, violates contractual accuracy)
