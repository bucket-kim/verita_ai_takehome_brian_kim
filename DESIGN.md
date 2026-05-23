# Metered API Billing System - Design Document

## 1. Data Model

The system uses 11 models across four Django apps. Core entities: Customer, UsageEvent, UsageWindow, Invoice.

**Customer** has UUID primary keys, unique email, and ApiKeys with SHA256 key_hash. ApiKeys store key_prefix (first 8 chars) for display and nullable revoked_at for revocation. Customer implements `is_authenticated` for DRF's IsAuthenticated permission.

**UsageEvent** has a UNIQUE index on `request_id` for idempotency. When clients POST to `/v1/events`, bulk_create(ignore_conflicts=True) silently skips duplicates. Without this index, duplicate submissions create phantom usage. The alternative (check before insert) races under concurrent submissions. The UNIQUE constraint lets the database handle deduplication atomically. Events have a (customer, event_timestamp) index for hourly aggregation queries. ForeignKeys use string references ("customers.Customer") for cross-app decoupling.

**UsageWindow** stores hourly totals with unique (customer, window_start) constraint preventing duplicate buckets. The finalized boolean marks closed windows. Late events after finalization create adjustment line items in the next billing cycle rather than recomputing past invoices.

**Invoice** stores monthly bills with (customer, status) index. **InvoiceLineItem** breaks down totals by pricing tier with units, unit_price_millicents, total_cents, and overridden boolean. PATCH modifications create AuditLog entries.

**AuditLog** is immutable: save() with existing pk raises PermissionError, delete() always raises PermissionError. Creates tamper-evident trail. entity_id is CharField for heterogeneous IDs.

**Cursor pagination** encodes "timestamp|id" in base64. Provides stable results under concurrent writes - new events don't shift page boundaries. Offset pagination causes page drift: 100 new events between page 1 and 2 creates duplicates. For billing reconciliation, correctness trumps simplicity. Fetches limit+1 to detect has_more without COUNT query.

**Scaling indexes**: At 10× load (~20k events/min), add partial index: `CREATE INDEX ON usage_event (customer_id, event_timestamp) WHERE finalized=false` to reduce aggregator scan cost. At 100× (~200k/min), partition UsageEvent by month using Postgres range partitioning to keep hot partition small and archive cold partitions.

## 2. Idempotency & Concurrency

**Event ingestion**: UNIQUE constraint on request_id + bulk_create(ignore_conflicts=True). EventsView bulk inserts, database skips conflicts, view queries back by request_id for 207 Multi-Status ("created"/"duplicate"). Handles concurrent identical request_ids without locking.

**Aggregator**: JobLock with select_for_update(skip_locked=True) prevents concurrent runs - second process exits immediately. Aggregation uses update_or_create() on UsageWindow with unique (customer, window_start). Concurrent aggregators compute identical total_units and upsert to same window. Idempotent.

**Webhook**: WebhookDelivery.get_or_create(external_id) inside transaction.atomic(). Returns existing record with created=False if duplicate, view returns "already_processed" instead of marking invoice paid again.

**Ops credit**: Unique nullable idempotency_key on Credit model. select_for_update() on Customer row serializes credit operations. Concurrent requests: Thread A creates, Thread B waits then finds existing. Frontend generates UUID via crypto.randomUUID() on button click.

## 3. Aggregation Pipeline

Three stages: **raw events → hourly windows → monthly invoices**. Each stage recomputable from inputs, but issued invoices are immutable.

**Stage 1**: POST /v1/events writes immutable UsageEvent rows. request_id deduplication allows safe resubmission.

**Stage 2**: APScheduler runs aggregate_usage_windows every 5 minutes. Queries unfinalized UsageEvents, groups by customer + TruncHour(event_timestamp), sums units, update_or_creates UsageWindow. Fully recomputable from source events. Windows older than current month get finalized at invoice generation.

**Stage 3**: generate_invoices runs monthly (1st at 00:00 UTC). Manual month arithmetic (no dateutil), queries finalized UsageWindows, applies tiered pricing, creates Invoice + InvoiceLineItem via get_or_create(customer, period_start, period_end). "Issued" status = immutable.

**Late-arriving events**: If window unfinalized, next aggregator includes it. If finalized (invoice issued), create adjustment line item in next invoice period. Example: 100k units billed in January, 5k late event arrives in February with January timestamp → February invoice includes "January usage adjustment: 5,000 units @ $0.01 = $50.00". Trades billing lag for invoice immutability.

**Recomputable vs Immutable**: UsageWindows recomputable until finalized. Draft invoices recomputable. Issued invoices immutable by convention. AuditLog programmatically immutable.

## 4. Failure Modes

**Aggregator backlog at 2000 events/sec**: 600k events per 5-minute interval. If aggregator takes >5min, it falls behind. skip_locked causes next run to exit. Symptoms: unfinalized windows grow, invoices show $0. Detection: alert if events with event_timestamp >1hr ago not in UsageWindow count >1M. Mitigation: modulo sharding (WHERE MOD(customer.id, N) = worker_id) with N workers, each with own JobLock. N=10 reduces load to 60k/interval. Alternative: streaming with Flink + Redis counters, snapshot at month-end.

**Invoice generation crash**: Process crashes mid-run after partial commits. get_or_create skips customers with existing invoices, missing customers never get invoices. Detection: on 1st at 01:00, alert if invoices <90% of active customers. Mitigation: get_or_create makes job resumable. Add `./manage.py generate_invoices --month=2024-01` for manual retry. Alternative: Celery/RQ with per-customer tasks, unprocessed tasks auto-retry.

**Clock skew**: Customer clock 65min fast/slow puts events in wrong hourly window. UsageWindows don't correlate with traffic. Detection: alert if abs(event_timestamp - ingested_at) >5min for >1% of customer events. Mitigation: reject events with abs(event_timestamp - now()) >1hr via 400 Bad Request. Soft launch: log for 2 weeks, then enforce. Provide /v1/time endpoint. Alternative: use ingested_at as authoritative (loses batch historical accuracy).

## 5. Threat Model

**Cross-tenant access**: Customer A tries GET /v1/invoices/{uuid_B}. Defense: TenantScopedAPIView sets self.customer = request.user, filters Invoice.objects.filter(customer=self.customer, pk=uuid) returning 404 for cross-tenant access. UUID primary keys have 2^122 entropy, brute-force infeasible.

**API key brute force**: Attack 32-char hex keys (2^128 entropy). Defense: SHA256 hash + database lookup on key_hash, constant-time. 10k guesses/sec takes 10^28 years. Missing: rate limiting on failed auth (should 429 after 10 failures/min per IP, alert after 100 failures per key_prefix).

**Fraudulent credit issuance**: Ops issues $10k credit. Defense: immutable AuditLog with actor, before_value, after_value. Missing: approval workflow for large credits (>$500 should require two-person approval via PendingCredit model).

**Invoice line item override**: Ops reduces invoice $1k→$10. Defense: PATCH sets overridden=true, creates AuditLog, exposes audit trail via GET. Weakness: no required reason field.

**Webhook replay**: Capture legitimate payment_id=12345, replay. Defense: WebhookDelivery.get_or_create(external_id), returns "already_processed" on duplicate.

**Webhook forgery**: Craft fake payload. Defense: HMAC-SHA256 signature with hmac.compare_digest (constant-time), reject on mismatch. Weakness: no timestamp validation (should reject webhooks >5min old).

## 6. Trade-offs

**Cursor vs offset pagination**: Chose cursor ("timestamp|id" base64) for /v1/usage and /ops/customers. Provides stable results under concurrent writes - WHERE (timestamp, id) > (cursor_timestamp, cursor_id) ORDER BY timestamp, id LIMIT N+1. Offset pagination (LIMIT N OFFSET M) shifts boundaries: 100 new events between page 1-2 creates duplicates. For billing reconciliation, correctness trumps simplicity. Cost: opaque cursors, no arbitrary page jumps, no total count. Acceptable for chronological data.

**Hourly windows vs per-event aggregation**: Chose hourly UsageWindow pre-aggregation (5min job). Invoice generation sums ~720 windows vs 1M events: 100ms vs 10sec per customer. At 1000 customers: 100sec vs 10,000sec. 5min lag acceptable. Rejected real-time: requires distributed counter (Redis/Cassandra) for 2000 events/sec. INCR becomes bottleneck. Cost: finalization logic, late event handling. Benefit: no Redis dependency (one less failure mode). At 200 events/sec peak, simplicity wins.

## 7. What You Didn't Build

**Real-time usage alerts**: No spending thresholds. Needs: Threshold model (customer_id, amount_cents, notification_method), background job comparing windows to thresholds, AlertHistory dedup. 2-3 days.

**Proration**: Can't switch plans mid-month. Needs: PlanChange model (effective_date), invoice generation splitting month into segments, CreditLineItem for unused prepaid. Complex logic (30 vs 31-day months). 5 days.

**Dunning/retry**: No payment failure handling. Needs: payment_failed status, retry schedule (3/7/14 days), email notifications, service suspension. 3-4 days retry logic, 2 days suspension.

**Distributed tracing**: No request IDs through stack. Needs: OpenTelemetry with span IDs linking event POST → aggregation → invoice generation. 2 days tracing, 1 day Jaeger/Tempo backend.

**API versioning**: No /v2 framework. Changing events format requires eternal backwards compatibility or breaking clients. Needs: version negotiation (Accept header/URL), deprecation policy. 1 day routing, ongoing maintenance cost.

**Multi-currency**: USD only. Needs: Currency field on Customer/Invoice, exchange rate lookup at generation, storing original + converted amounts. Complex (rate source? post-issuance changes?). 4-5 days.

**Anomaly detection**: No spike alerts. Needs: baseline (30-day average), threshold detection (current >5× baseline), alert pipeline. 2-3 days statistical approach.
