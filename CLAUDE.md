# CLAUDE.md

Metered API billing system with Django REST Framework backend and React frontend.

## Key Conventions

- **Django models**: Use string references for cross-app ForeignKeys (e.g., `"customers.Customer"`)
- **Money handling**: IntegerField (cents), millicents for pricing - no floats. All pricing arithmetic in millicents (integer), convert to cents only at Invoice.total_cents to avoid float precision errors
- **Immutable models**: Override save/delete to raise PermissionError (e.g., AuditLog) - programmatic immutability for tamper-evident audit trail
- **Constraints over comments**: Use database UNIQUE constraints for business rules (request_id uniqueness ensures idempotency), not just code-level validation

## Directory Structure

- `backend/apps/` - Django apps: `billing` (invoices, line items), `customers` (Customer, ApiKey), `ops` (admin endpoints, JobLock), `usage` (events, aggregated windows)
- `frontend/src/` - React app: `api/` (axios client), `hooks/` (data fetching), `pages/` (routes), `components/` (shared UI), `types/` (TypeScript interfaces)

## API Architecture Patterns

- **URL structure**: Customer endpoints at `/v1/*`, ops at `/ops/*`, webhooks at `/webhooks/*` (all mounted at root in config/urls.py)
- **Authentication**: ApiKeyAuthentication (X-API-Key header, SHA256 hash lookup) for /v1, OpsTokenAuthentication (X-Ops-Token header) for /ops, HMAC signature verification for webhooks
- **Tenant scoping**: TenantScopedAPIView base class sets `self.customer = request.user` in initial() - enforced at dependency layer (not in views), extend for all /v1 views. Filters: Invoice.objects.filter(customer=self.customer) prevents cross-tenant access
- **Cursor pagination**: Base64-encoded `timestamp|id` format for stateless pagination. Chosen over offset because new rows don't shift page boundaries - critical for billing reconciliation where accuracy > simplicity
- **Idempotency guarantees**:
  - Events: UNIQUE(request_id) + bulk_create(ignore_conflicts=True) = database-level deduplication, concurrent threads can't create duplicates
  - Webhooks: WebhookDelivery.get_or_create(external_id) = replays return "already_processed" without double-marking invoices paid
  - Credits: select_for_update() on Customer + unique idempotency_key = concurrent ops can't double-credit
  - Aggregation: update_or_create() with unique(customer, window_start) = running twice produces identical results
- **Events API format**: POST /v1/events accepts `{"events": [{request_id, api_key_id, endpoint, units, timestamp}]}` bulk format, returns 207 Multi-Status with per-event "created"/"duplicate"
- **Concurrency safety**: select_for_update() when modifying customer balances/credits, transaction.atomic() for multi-step updates, JobLock with skip_locked=True prevents concurrent background jobs
- **Security**: hmac.compare_digest() for constant-time comparison (webhook signatures, tokens) to prevent timing attacks. See DESIGN.md Section 5 for full threat model (cross-tenant, brute force, fraudulent credits, webhook forgery)
- **Audit logging**: Create AuditLog entries for sensitive ops actions with before_value/after_value. Immutable (save/delete raise PermissionError) for tamper evidence

## Background Jobs and Pricing

- **Job locking**: Use select_for_update(skip_locked=True) on JobLock model to prevent concurrent execution
- **APScheduler setup**: Check `os.environ.get('RUN_MAIN') == 'true'` in apps.py ready() to avoid duplicate scheduler in Django reloader
- **Tiered pricing**: All arithmetic in millicents (integer), convert to cents only at Invoice.total_cents. Tiers: 0-10k units @ 0¢, 10k-100k @ 0.1¢, 100k+ @ 0.05¢
- **aggregate_usage_windows**: Runs every 5min, uses TruncHour() to group events by customer+hour
- **generate_invoices**: Runs 1st of month at midnight, applies 3-tier pricing (0/100/50 millicents)

## Index Strategy (Why Each Index Exists)

**Indexes match the queries we actually run:**

- **UsageEvent(request_id)** UNIQUE: Idempotency deduplication in bulk_create(ignore_conflicts=True). Without this, duplicate POSTs create phantom usage
- **UsageEvent(customer, event_timestamp)**: Aggregator query `GROUP BY customer, TruncHour(event_timestamp)` runs every 5min. Without this index, full table scan on 30k+ events
- **UsageWindow(customer, window_start)** UNIQUE: Prevents duplicate hourly buckets. Used by aggregator's update_or_create() upsert
- **Invoice(customer, status)**: Ops queries `Invoice.objects.filter(customer=..., status='issued')` to find unpaid invoices
- **ApiKey(key_hash)**: Authentication lookup on every /v1 request. SHA256 hash prevents plaintext key storage
- **ApiKey(customer, revoked_at)**: Filter active keys per customer. NULL revoked_at = active

**At scale (see DESIGN.md for details):**
- **10× load**: Add partial index `(customer_id, event_timestamp) WHERE finalized=false` - aggregator only processes unfinalized events
- **100× load**: Partition UsageEvent by month (Postgres range partitioning) - keeps hot partition small, archive cold months

## Scaling & Performance

**Current capacity (seed data scale):**
- 20 customers, ~30k events over 60 days = ~200 events/sec peak
- Aggregator processes 5min windows (1.5k events/window) in <10 sec
- Invoice generation for 20 customers: <5 sec
- Database: Postgres single instance, ~100MB data

**What breaks first:**
1. **Aggregator at 2000 events/sec sustained**: 600k events per 5min window. If processing takes >5min, skip_locked causes next run to exit. Unfinalized windows pile up, invoices show $0 usage
2. **Invoice generation at 10k+ customers**: Synchronous iteration takes >10min, risks timeout/crash mid-run leaving partial invoices
3. **Database at 100M+ events**: Queries on UsageEvent slow despite indexes, need partitioning

**Scales with known fix:**
- **Event ingestion**: Horizontally scalable (stateless API, bulk_create), add app servers behind load balancer
- **Aggregator backlog**: Modulo sharding `WHERE MOD(customer.id, N) = worker_id`, N workers = N× throughput. N=10 handles 2000/sec
- **Invoice generation**: Async queue (Celery/RQ) with per-customer tasks, auto-resumes after crash
- **Database reads**: Add read replicas for /v1 endpoints (events, invoices), write to primary

**Won't scale without rearchitecture:**
- **Single aggregator process at 10k+ events/sec**: Need streaming (Apache Flink) + distributed counters (Redis), batch approach hits limits
- **Synchronous jobs for 100k+ customers**: Need distributed task queue with multiple workers, APScheduler single-threaded

**Query performance (typical):**
- GET /v1/invoices (list): 10-30ms (index on customer)
- POST /v1/events (bulk 100): 50-100ms (bulk_create, index on request_id)
- Aggregator (5min window): 5-15sec (index on customer, event_timestamp)
- Invoice generation (per customer): 200-500ms (depends on window count)

## Operational Debugging

**How ops debugs a wrong invoice:**
1. Get invoice: `Invoice.objects.get(id='uuid')` - check period_start, period_end, total_cents, status
2. Check line items: `invoice.line_items.all()` - verify units, unit_price_millicents, overridden flag
3. If overridden: `AuditLog.objects.filter(entity_type='InvoiceLineItem', entity_id=str(line_item.id))` - see who changed what when
4. Trace to windows: `UsageWindow.objects.filter(customer=customer, window_start__gte=period_start, window_start__lt=period_end)` - sum total_units should match invoice
5. Trace to raw events: `UsageEvent.objects.filter(customer=customer, event_timestamp__gte=window_start, event_timestamp__lt=window_end)` - verify event count
6. Check for late arrivals: `UsageEvent.objects.filter(customer=customer, event_timestamp__lt=period_end, ingested_at__gte=period_end)` - late events create adjustments in next invoice
7. Manual fix: PATCH /ops/invoices/{uuid}/line-items/{id} with reason, creates audit log

**Observability: What to alert on**
- **Aggregator behind**: `JobLock.objects.get(name='aggregate').locked_at` >10min old while events piling up
- **Unprocessed events**: Count events with `event_timestamp < now() - 1hr` not in any UsageWindow >1M
- **Invoice generation incomplete**: On 1st at 01:00, `Invoice.objects.filter(period_start=last_month).count() < 0.9 * active_customer_count`
- **Clock skew**: >1% of customer's events have `abs(event_timestamp - ingested_at) > 5min`
- **Failed auth spike**: >100 failed API key lookups in 1min for same key_prefix (potential brute force)
- **Webhook signature failures**: >10 failed HMAC verifications in 1min (potential attack)

**Migration story:**
- Schema changes: `docker-compose exec backend python manage.py makemigrations`, test locally, then `migrate`
- Zero-downtime: Avoid locking ALTER TABLE on UsageEvent (large table). Use Django `migrations.RunPython` for data migrations
- Rollback: Keep previous docker image tag, `docker-compose down && git checkout <commit> && docker-compose up`
- Add column: Safe (no lock). Modify column: Requires backfill, use batched UPDATE
- Partitioning: Create new partitioned table, copy data in batches, swap table names

## Trade-offs & Design Decisions

**See DESIGN.md Sections 6-7 for detailed analysis.** Key decisions:

**Cursor vs offset pagination:**
- Chose: Cursor (base64 "timestamp|id") for stable results under concurrent writes
- Rejected: Offset (LIMIT N OFFSET M) - 100 new events between pages creates duplicates
- Why: Billing reconciliation needs correctness > simplicity. Users export usage for accounting
- Cost: Can't jump to arbitrary pages, no total count. Acceptable for chronological data

**Hourly windows vs real-time aggregation:**
- Chose: Hourly UsageWindow pre-aggregation (5min job)
- Rejected: Real-time Redis counters incremented per event
- Why: Query cost predictability (720 windows vs 1M events), simpler ops (no Redis = one less failure mode)
- Cost: 5min lag, late event handling complexity. At 200/sec peak, simplicity wins

**Late events - adjustment vs recomputation:**
- Chose: Adjustment line items in next invoice ("January adjustment: +5k units")
- Rejected: Recompute past invoices, reissue to customer
- Why: Invoice immutability (accounting/legal), simpler auditing
- Cost: Billing lag for late events (pay next month). Acceptable for rare case

**UUID vs integer IDs:**
- Chose: UUIDs for Customer, Invoice, UsageEvent (2^122 entropy)
- Rejected: Sequential integers
- Why: Prevents enumeration attacks, no "customer has 73 invoices" info leak
- Cost: 16 bytes vs 4 bytes, slightly slower joins. Worth it for security

**Immutable AuditLog:**
- Chose: Programmatic immutability (PermissionError on save/delete)
- Rejected: Database-enforced (triggers, permissions)
- Why: Simpler testing, explicit in Python code, same tamper evidence
- Cost: Not enforced if direct SQL. Acceptable - ops shouldn't bypass ORM

**Honest assessment - what we'd do differently:**
- **At 10x scale**: Use Celery for invoice generation (better resumability), current APScheduler is simpler but fragile for 1000+ customers
- **For real-time needs**: Need streaming aggregation (Flink), current 5min lag acceptable for MVP
- **With more time**: Add event timestamp validation (reject if >1hr drift), currently trust client which enables batch imports but allows clock skew

## Build and Test Commands

### Quick Start

- Copy environment template: `cp .env.example .env` (edit SECRET_KEY, WEBHOOK_SECRET, OPS_TOKEN for production)
- First run: `docker-compose up --build` (builds images and starts services)

### Development and Build

- Build stack: `docker-compose build`
- Spin up full stack: `docker-compose up`
- Start services detached: `docker-compose up -d`
- Build frontend: `cd frontend && tsc -b && vite build`

### Seeding and Testing

- Seed test data: `docker-compose exec backend python manage.py seed`
  Creates 20 customers, ~30k events over 60 days, aggregates windows, generates invoices
  Prints sample API key - save it for testing endpoints
- Access postgres: `psql postgresql://postgres:postgres@localhost:5432/metered_billing`
- Query data counts: `docker-compose exec backend python manage.py shell -c "from apps.customers.models import Customer; print(Customer.objects.count())"`
- Test with API key: `curl -H "X-API-Key: sk_..." http://localhost:8000/v1/invoices`
- Create test customer: `docker-compose exec backend python manage.py shell -c "import hashlib; from apps.customers.models import Customer, ApiKey; c, _ = Customer.objects.get_or_create(email='test@example.com', defaults={'name': 'Test Customer'}); ApiKey.objects.filter(customer=c).delete(); key = 'sk_test_12345678901234567890123456789012'; ApiKey.objects.create(customer=c, key_hash=hashlib.sha256(key.encode()).hexdigest(), key_prefix=key[:8]); print(f'API Key: {key}')"`

### Linting and Formatting

- Lint and fix frontend: `cd frontend && npm run lint`
- Lint backend (black): `docker-compose exec backend black .`
- Check types (frontend): `cd frontend && npx tsc --noEmit`

### Testing

- **Complete test workflow**: `docker-compose build && docker-compose up -d && docker-compose exec backend pytest tests/ -v && cd frontend && npm run lint && npx tsc --noEmit && npm run build`
- Run all frontend checks: `cd frontend && npm run lint && npx tsc --noEmit && npm run build`
- Run backend tests: `docker-compose exec backend pytest`
- Run specific test: `docker-compose exec backend pytest tests/test_name.py -v`
- Run tests with details: `docker-compose exec backend pytest tests/ -v --tb=long`
- Run makemigrations: `docker-compose exec backend python manage.py makemigrations customers usage billing ops`
- Run database migrations: `docker-compose exec backend python manage.py migrate`

**Note:** Backend service must be running for `docker-compose exec` commands. Black formatter not included in Docker image - style checking must be done locally before commit

## Testing Patterns

- **pytest fixtures**: Define shared test data in conftest.py (customers, API keys, tokens)
- **Threading tests**: Use `@pytest.mark.django_db(transaction=True)` for concurrent tests
- **Webhook tests**: Use `api_client.generic()` for exact request body control (signature verification)
- **EventsView format**: POST to `/v1/events` with `{"events": [...]}` bulk format, returns 207 status
- **Idempotency testing**: Test same operation from multiple threads with same idempotency key
- **Test the bits that would break in production, not getters**:
  - test_concurrent_ingestion.py: 10 threads post same request_id, verify single UsageEvent created (tests idempotency race)
  - test_double_credit_prevention.py: 5 threads issue credit with same idempotency_key, verify single Credit (tests select_for_update lock)
  - test_tiered_pricing.py: 150k units → verify $11,500.00 invoice (tests millicents arithmetic, no float errors)
  - test_audit_log_immutability.py: Try to modify/delete AuditLog, verify PermissionError raised
  - Don't test: trivial getters, Django ORM basics, framework functionality

## Common Patterns

- **Customer as user object**: Customer model needs `is_authenticated` property for DRF's IsAuthenticated permission
- **Management commands**: Create in `apps/<app>/management/commands/<name>.py` with `__init__.py` files in parent dirs
- **Month arithmetic**: Avoid external deps - use manual month/year calculation instead of dateutil.relativedelta
- **AuditLog entity_id queries**: Convert integer IDs to strings before filtering (entity_id is CharField, not IntegerField)

## Documentation Standards

- **Design documents**: Target 1800-2200 words, dense technical prose with specific numbers over narrative
- **Phase execution**: Execute tasks from `.claude/phases/*.md` - these define structured workflows with specific deliverables
- **Word count verification**: Use `wc -w <file>` to check documentation meets length requirements
- **Writing style**: Preserve specifics (numbers, mechanisms, commands), remove verbose explanations and narrative fluff
- **Rubric evaluation**: 8 categories - Data model & integrity (18%), Concurrency & correctness (18%), Scaling reasoning (13%), API & frontend craft (13%), Security & isolation (10%), Trade-off writeup (10%), Operational thinking (10%), Code quality & testing (8%). Target 90+ for grade A

## Frontend Development

- **TypeScript imports**: Use `import type { ... }` for type-only imports (verbatimModuleSyntax enabled)
- **React Router v7**: Import from `react-router` package (BrowserRouter, Routes, Route, Link, useNavigate, useParams)
- **Directory structure**: `src/{api,hooks,pages,components,types}` - follow this pattern
- **Protected routes**: Check `localStorage.getItem('apiKey')`, redirect to `/customer/login` if missing
- **Recharts**: Wrap charts in ResponsiveContainer, use AreaChart for time series
- **Data fetching hooks**: Wrap fetch functions in useCallback, disable `react-hooks/set-state-in-effect` rule for initial data fetch in useEffect
- **ESLint config for data fetching**: Add `'react-hooks/set-state-in-effect': 'off'` to eslint.config.js rules - initial data fetching in useEffect is the correct pattern for this app
- **Loading/error states**: Always show loading spinner while fetching, error message on failure, empty state when no data. Not afterthoughts - design them upfront
- **Money-moving operations**:
  - Issue Credit button: Shows confirmation dialog ("Issue $X.XX credit?"), generates idempotency token on click via `crypto.randomUUID()`
  - Token included in POST header `x-idempotency-key: <uuid>`, prevents double-submit if user clicks twice
  - Disable button after click until response returns (loading state)
- **Frontend dev server**: `npm run dev` starts Vite at localhost:5173, auto-reloads on changes
- **Testing UI**: Use sample API key from `python manage.py seed` output
- **Vite in Docker**: Add `server: { host: '0.0.0.0', port: 5173 }` to vite.config.ts for external access
- **CORS headers**: Custom headers (`x-api-key`, `x-ops-token`, `x-idempotency-key`) must be in CORS_ALLOW_HEADERS in dev.py
- **Frontend restart**: Run `docker-compose restart frontend` after adding new pages/components for proper loading
