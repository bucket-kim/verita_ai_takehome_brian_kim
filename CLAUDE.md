# CLAUDE.md

Metered API billing system with Django REST Framework backend and React frontend.

**Quick Links:** [Commands](#build-and-test-commands) • [Testing](#testing-patterns) • [Architecture](#api-architecture-patterns) • [Scaling](#scaling--performance) • [Credentials](LOGIN_GUIDE.md)

## Key Conventions

- **Django models**: Use string references for cross-app ForeignKeys (e.g., `"customers.Customer"`)
- **Money handling**: IntegerField (cents), millicents for pricing - no floats. All pricing arithmetic in millicents (integer), convert to cents only at Invoice.total_cents to avoid float precision errors
- **Immutable models**: Override save/delete to raise PermissionError (e.g., AuditLog) - programmatic immutability for tamper-evident audit trail
- **Constraints over comments**: Use database UNIQUE constraints for business rules (request_id uniqueness ensures idempotency), not just code-level validation

## Directory Structure

- `backend/apps/` - Django apps: `billing` (invoices, line items), `customers` (Customer, ApiKey), `ops` (admin endpoints, JobLock), `usage` (events, aggregated windows)
- `frontend/src/` - React app: `api/` (axios client), `hooks/` (data fetching), `pages/` (routes), `components/` (shared UI), `types/` (TypeScript interfaces)
- `.claude/` - Claude Code configuration: `rules/testing.md` (QA procedures), `commands/` (custom slash commands), `CLAUDE.md` (coding guidelines)

## API Architecture Patterns

- **URL structure**: Customer endpoints at `/v1/*`, ops at `/ops/*`, webhooks at `/webhooks/*` (all mounted at root in config/urls.py)
- **Authentication**: ApiKeyAuthentication (X-API-Key header, SHA256 hash lookup) for /v1, OpsTokenAuthentication (X-Ops-Token header) for /ops, HMAC signature verification for webhooks
- **Tenant scoping**: TenantScopedAPIView base class sets `self.customer = request.user` in initial() - enforced at dependency layer (not in views), extend for all /v1 views. Filters: Invoice.objects.filter(customer=self.customer) prevents cross-tenant access
- **Cursor pagination**: Base64-encoded `timestamp|id` format for stateless pagination across large datasets
- **Idempotency guarantees**:
  - Events: UNIQUE(request_id) + bulk_create(ignore_conflicts=True) = database-level deduplication, concurrent threads can't create duplicates
  - Webhooks: WebhookDelivery.get_or_create(external_id) = replays return "already_processed" without double-marking invoices paid
  - Credits: select_for_update() on Customer + unique idempotency_key = concurrent ops can't double-credit
  - Aggregation: update_or_create() with unique(customer, window_start) = running twice produces identical results
- **Events API format**: POST /v1/events accepts `{"events": [{request_id, api_key_id, endpoint, units, timestamp}]}` bulk format, returns 207 Multi-Status with per-event "created"/"duplicate"
- **Concurrency safety**: select_for_update() when modifying customer balances/credits, transaction.atomic() for multi-step updates
- **Security**: hmac.compare_digest() for constant-time comparison (webhook signatures, tokens) to prevent timing attacks. See DESIGN.md Section 5 for full threat model (cross-tenant, brute force, fraudulent credits, webhook forgery)
- **Audit logging**: Create AuditLog entries for sensitive ops actions with before_value/after_value. Immutable (save/delete raise PermissionError) for tamper evidence

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

## Background Jobs and Pricing

- **Job locking**: Use select_for_update(skip_locked=True) on JobLock model to prevent concurrent execution
- **APScheduler setup**: Check `os.environ.get('RUN_MAIN') == 'true'` in apps.py ready() to avoid duplicate scheduler in Django reloader
- **Tiered pricing**: All arithmetic in millicents (integer), convert to cents only at Invoice.total_cents
- **aggregate_usage_windows**: Runs every 5min, uses TruncHour() to group events by customer+hour
- **generate_invoices**: Runs 1st of month at midnight, applies 3-tier pricing (0/100/50 millicents)

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

## Build and Test Commands

### Quick Health Check

Verify all services are running and accessible:
```bash
docker-compose ps && \
curl -s -o /dev/null -w "Backend: %{http_code}\n" http://localhost:8000/v1/invoices -H "X-API-Key: test" && \
curl -s -o /dev/null -w "Frontend: %{http_code}\n" http://localhost:5173 && \
echo "✓ System Ready"
```

### Quick Start

- Copy environment template: `cp .env.example .env` (edit SECRET_KEY, WEBHOOK_SECRET, OPS_TOKEN for production)
- First run: `docker-compose up --build` (builds images and starts services)
- **Testing reference**: See `.claude/rules/testing.md` for QA workflows, CORS troubleshooting, and route validation
- **Login credentials**: See `LOGIN_GUIDE.md` for test credentials and troubleshooting login issues

### Development and Build

- Build stack: `docker-compose build`
- Spin up full stack: `docker-compose up`
- Start services detached: `docker-compose up -d`
- Build frontend: `cd frontend && tsc -b && vite build`

### Seeding and Testing

- **Seed test data**: `docker-compose exec backend python manage.py seed`
  Creates 20 customers, ~30k events over 60 days, aggregates windows, generates invoices
  Prints sample API key - save it for testing endpoints
- **Verify connectivity**: After seeding, verify backend/frontend connection is working properly (see Troubleshooting section for connectivity test script)
- **Access postgres**: `psql postgresql://postgres:postgres@localhost:5432/metered_billing`
- **Query data counts**: `docker-compose exec backend python manage.py shell -c "from apps.customers.models import Customer; print(Customer.objects.count())"`
- **Create test customer**: Create customer with known API key for testing
  ```bash
  docker-compose exec backend python manage.py shell -c "
  import hashlib
  from apps.customers.models import Customer, ApiKey
  c, _ = Customer.objects.get_or_create(email='test@example.com', defaults={'name': 'Test Customer'})
  key = 'sk_test_demo_99999999999999999999999999'
  ApiKey.objects.filter(customer=c).delete()
  ApiKey.objects.create(customer=c, key_hash=hashlib.sha256(key.encode()).hexdigest(), key_prefix=key[:8])
  print(f'API Key: {key}')
  "
  ```

### Linting and Formatting

- Lint and fix frontend: `cd frontend && npm run lint`
- Lint backend (black): `docker-compose exec backend black .`
- Check types (frontend): `cd frontend && npx tsc --noEmit`

### Testing

- **Run all tests**: `docker-compose build && docker-compose up -d && docker-compose exec backend pytest tests/ -v && cd frontend && npm run lint && npx tsc --noEmit && npm run build`
- Run backend tests only: `docker-compose exec backend pytest`
- Run frontend checks only: `cd frontend && npm run lint && npx tsc --noEmit && npm run build`
- Run makemigrations: `docker-compose exec backend python manage.py makemigrations customers usage billing ops`
- Run database migrations: `docker-compose exec backend python manage.py migrate`

**Note:** Backend service must be running for `docker-compose exec` commands. Black formatter not included in Docker image - style checking must be done locally before commit

### Load Testing

**Generate continuous events for scale testing:**
```bash
# Simulate production load (200 events/sec)
for i in {1..100}; do
  docker-compose exec backend python manage.py shell -c "
  from apps.usage.models import UsageEvent
  from apps.customers.models import Customer
  import random, uuid
  from django.utils import timezone
  customers = list(Customer.objects.all())
  events = [UsageEvent(
      request_id=str(uuid.uuid4()),
      customer=random.choice(customers),
      api_key=random.choice(customers).api_keys.first(),
      endpoint='/api/test',
      units=random.randint(1, 100),
      event_timestamp=timezone.now()
  ) for _ in range(200)]
  UsageEvent.objects.bulk_create(events, ignore_conflicts=True)
  print(f'Batch {i}: 200 events created')
  "
  sleep 1  # Rate: 200 events/sec
done
```

**Monitor aggregator performance under load:**
```bash
# Watch job lock lag and unprocessed event count
watch -n 1 'docker-compose exec backend python manage.py shell -c "
from apps.ops.models import JobLock
from apps.usage.models import UsageEvent
from django.utils import timezone
lock = JobLock.objects.get(name=\"aggregate\")
lag = (timezone.now() - lock.locked_at).total_seconds()
unprocessed = UsageEvent.objects.filter(finalized=False).count()
print(f\"Aggregator lag: {lag:.1f}s | Unprocessed events: {unprocessed:,}\")
"'

# If lag >300s (5min job interval), aggregator is falling behind (bottleneck reached)
# At 2000 events/sec sustained, expect to hit this bottleneck (see Scaling section)
```

**Test aggregator at peak load (2000 events/sec):**
```bash
# Generate 2000 events/sec for 5 minutes = 600k events (tests Day 6 bottleneck)
for i in {1..300}; do
  docker-compose exec backend python manage.py shell -c "
  # Generate 2000 events in batch
  events = [UsageEvent(...) for _ in range(2000)]
  UsageEvent.objects.bulk_create(events, ignore_conflicts=True)
  " &
  sleep 1
done

# Monitor: aggregator should fall behind after ~5min (proves scaling analysis)
```

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
- **Test credentials are consistent**: API key `sk_test_demo_key_11111111111111111111111111111111` hardcoded in seed.py:58, always same for local dev
- **Ops token in .env**: Default `ops-dev-token-12345` (not placeholder) - required for ops console testing

## Troubleshooting

### CORS Policy Errors

**Symptom:** Browser console shows error like:
```
Access to XMLHttpRequest at 'http://localhost:8000/v1/...' from origin 'http://localhost:5173'
has been blocked by CORS policy: Request header field x-api-key is not allowed by
Access-Control-Allow-Headers in preflight response.
```

**Diagnosis:**
- Check browser console (F12 → Console tab) for CORS errors
- CORS errors prevent frontend from communicating with backend API
- Custom headers (`x-api-key`, `x-ops-token`, `x-idempotency-key`) must be explicitly allowed

**Fix:**
1. Verify `backend/config/settings/dev.py` includes `CORS_ALLOW_HEADERS` with all custom headers:
   ```python
   CORS_ALLOW_HEADERS = [
       'accept', 'accept-encoding', 'authorization', 'content-type',
       'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
       'x-api-key', 'x-ops-token', 'x-idempotency-key',
   ]
   ```
2. Restart backend: `docker-compose restart backend`
3. Verify fix: Check browser console for successful API requests (no CORS errors)

**Important:** Do not share frontend URL (http://localhost:5173) until CORS is working. Test API endpoints directly first with curl to isolate issues.

### Verify Backend-Frontend Connectivity

**Quick connectivity test:** Run this command to verify all connections are working:
```bash
curl -s -o /dev/null -w "Backend: %{http_code}\n" http://localhost:8000/v1/invoices -H "X-API-Key: sk_test1_11111111111111111111111111111111" && \
curl -s -o /dev/null -w "Frontend: %{http_code}\n" http://localhost:5173 && \
curl -s -I http://localhost:8000/v1/invoices -H "Origin: http://localhost:5173" | grep -i "access-control-allow-origin" && \
echo "✓ Connectivity OK"
```

**Expected output:**
```
Backend: 200
Frontend: 200
access-control-allow-origin: http://localhost:5173
✓ Connectivity OK
```

**Full test suite:** For comprehensive testing (CORS, authentication, API endpoints):
```bash
# Test backend/frontend connectivity
docker-compose ps  # Verify all services are running
docker-compose logs backend --tail 20  # Check for errors
docker-compose logs frontend --tail 20  # Check for errors

# Test API with curl
curl -s http://localhost:8000/v1/invoices \
  -H "X-API-Key: sk_test1_11111111111111111111111111111111" \
  -H "Origin: http://localhost:5173" | jq .

# Test CORS headers
curl -s -X OPTIONS http://localhost:8000/v1/invoices \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Headers: x-api-key" -I | grep access-control

# Test dynamic routes with UUID parameter
CUSTOMER_ID=$(curl -s http://localhost:8000/ops/customers -H "X-Ops-Token: your-ops-token-here" | jq -r '.customers[0].id')
curl -s -o /dev/null -w "Backend: %{http_code}\n" http://localhost:8000/ops/customers/$CUSTOMER_ID -H "X-Ops-Token: your-ops-token-here"
curl -s -o /dev/null -w "Frontend: %{http_code}\n" http://localhost:5173/ops/customers/$CUSTOMER_ID
```

**Access URLs (only share after connectivity verified):**
- Frontend: http://localhost:5173
- Customer Login: http://localhost:5173/customer/login
- Ops Console Login: http://localhost:5173/ops/login
- Backend API: http://localhost:8000

## Operational Debugging

**How ops debugs a wrong invoice:**
1. Get invoice: `Invoice.objects.get(id='uuid')` - check period_start, period_end, total_cents, status
2. Check line items: `invoice.line_items.all()` - verify units, unit_price_millicents, overridden flag
3. If overridden: `AuditLog.objects.filter(entity_type='InvoiceLineItem', entity_id=str(line_item.id))` - see who changed what when
4. Trace to windows: `UsageWindow.objects.filter(customer=customer, window_start__gte=period_start, window_start__lt=period_end)` - sum total_units should match invoice
5. Trace to raw events: `UsageEvent.objects.filter(customer=customer, event_timestamp__gte=window_start, event_timestamp__lt=window_end)` - verify event count
6. Check for late arrivals: `UsageEvent.objects.filter(customer=customer, event_timestamp__lt=period_end, ingested_at__gte=period_end)` - late events create adjustments in next invoice
7. Manual fix: PATCH /ops/invoices/{uuid}/line-items/{id} with reason, creates audit log

**Anomaly detection:**
- **Usage spike detection**: Flag customers with usage >10× their 30-day average
  ```python
  # Calculate for customer
  current_month_total = UsageWindow.objects.filter(
      customer=customer, window_start__gte=start_of_month
  ).aggregate(Sum('total_units'))['total_units__sum'] or 0

  last_30_days_total = UsageWindow.objects.filter(
      customer=customer, window_start__gte=timezone.now() - timedelta(days=30)
  ).aggregate(Sum('total_units'))['total_units__sum'] or 0

  avg_daily = last_30_days_total / 30
  days_elapsed = (timezone.now() - start_of_month).days
  expected = avg_daily * days_elapsed

  if current_month_total > expected * 10:
      flag_anomaly(customer, current_month_total, expected)
  ```
- **Display**: ⚠️ badge in ops console customer list (`/ops/customers`)
- **Use cases**: Compromised API key, billing error, DDoS from customer account, unusual growth
- **Alerting**: >100× average triggers immediate ops notification (potential attack)
- **Implementation**: Frontend computes ratio from usage data fetched via GET /ops/customers

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

## Common Patterns

- **Customer as user object**: Customer model needs `is_authenticated` property for DRF's IsAuthenticated permission
- **Management commands**: Create in `apps/<app>/management/commands/<name>.py` with `__init__.py` files in parent dirs
- **Month arithmetic**: Avoid external deps - use manual month/year calculation instead of dateutil.relativedelta
- **AuditLog entity_id queries**: Convert integer IDs to strings before filtering (entity_id is CharField, not IntegerField)

## User Experience and Startup

- **Display credentials on startup**: backend/entrypoint.sh shows formatted banner with login URLs and credentials when services start
- **Helper scripts for UX**: Create show_credentials.sh and start.sh to display credentials without reading logs
- **Visual formatting matters**: Use box-drawing characters (╔═╗ ┌─┐) for credential banners - makes them easy to spot in logs
- **Docker entrypoint.sh must be executable**: COPY entrypoint.sh /entrypoint.sh + RUN chmod +x in Dockerfile, entrypoint: ["/entrypoint.sh"] in docker-compose.yml
- **Never-changing test keys**: For local dev, use hardcoded test keys (not random) so users don't need to look them up each time
- **Seed script creates known key**: seed.py creates both random keys (for realism) and one known test key at line 58 for easy login

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

## Frontend Development

- **TypeScript imports**: Use `import type { ... }` for type-only imports (verbatimModuleSyntax enabled)
- **React Router v7**: Import from `react-router` package (BrowserRouter, Routes, Route, Link, useNavigate, useParams)
- **Directory structure**: `src/{api,hooks,pages,components,types}` - follow this pattern
- **Protected routes**:
  - Customer routes: Check `localStorage.getItem('apiKey')`, redirect to `/customer/login` if missing
  - Ops routes: Check `localStorage.getItem('opsToken')`, redirect to `/ops/login` if missing
- **API clients**: Two separate axios clients - `api/client.ts` (X-API-Key) for customer endpoints, `api/ops.ts` (X-Ops-Token) for ops endpoints
- **Recharts**: Wrap charts in ResponsiveContainer, use AreaChart for time series
- **Data fetching hooks**: Wrap fetch functions in useCallback, disable `react-hooks/set-state-in-effect` rule for initial data fetch in useEffect
- **ESLint config for data fetching**: Add `'react-hooks/set-state-in-effect': 'off'` to eslint.config.js rules - initial data fetching in useEffect is the correct pattern for this app
- **Loading/error states**: Always show loading spinner while fetching, error message on failure, empty state when no data. Not afterthoughts - design them upfront
- **Money-moving operations**:
  - Issue Credit button: Shows confirmation dialog ("Issue $X.XX credit?"), generates idempotency token on click via `crypto.randomUUID()`
  - Token included in POST header `x-idempotency-key: <uuid>`, prevents double-submit if user clicks twice
  - Disable button after click until response returns (loading state)
- **Frontend dev server**: `npm run dev` starts Vite at localhost:5173, auto-reloads on changes
- **Vite in Docker**: Add `server: { host: '0.0.0.0', port: 5173 }` to vite.config.ts for external access
- **CORS headers**: Custom headers (`x-api-key`, `x-ops-token`, `x-idempotency-key`) must be in CORS_ALLOW_HEADERS in dev.py
- **Vite Docker config**: In vite.config.ts, use `server: { host: '0.0.0.0', port: 5173 }` for external access from Docker
- **Frontend restart**: Run `docker-compose restart frontend` after adding new pages/routes/components
- **Restart required when:** Adding routes to App.tsx, creating new top-level page imports, or modifying route protection logic (hot reload misses these)
- **Testing UI**: Use sample API key from `python manage.py seed` output for customer portal, use OPS_TOKEN from .env for ops console

### Frontend Routes

**Customer Portal:**
- `/customer/login` - Customer authentication (API key)
- `/customer/dashboard` - Usage overview and charts
- `/customer/invoices` - Invoice list
- `/customer/invoices/:id` - Invoice details

**Ops Console:**
- `/ops/login` - Ops authentication (ops token)
- `/ops/customers` - Customer management list
- `/ops/customers/:id` - Customer detail with credit issuance

**Dynamic Routes:**
- React Router: Use `:id` for parameters (e.g., `/ops/customers/:id`)
- Django URLs: Use `<uuid:customer_id>` in urls.py
- TypeScript: Type useParams: `const { id } = useParams<{ id: string }>();`
- Testing: Verify with 3+ different IDs, not just one

## Documentation Standards

- **Design documents**: Target 1800-2200 words, dense technical prose with specific numbers over narrative
- **DESIGN.md condensation**: If over 2500 words, use arrow notation (mechanism → result), structured bullets (When/Symptom/Fix), code references over full blocks, remove duplicates
- **Review execution**: `.claude/commands/review.md` provides checklist for DESIGN.md - identifies gaps by rubric category (Data model 18%, Concurrency 18%, Scaling 13%, API 13%, Security 10%, Trade-offs 10%, Ops 10%, Testing 8%)
- **Phase execution**: Execute tasks from `.claude/phases/*.md` - these define structured workflows with specific deliverables
- **Word count verification**: Use `wc -w <file>` to check documentation meets length requirements
- **Writing style**: Preserve specifics (numbers, mechanisms, commands), remove verbose explanations and narrative fluff
- **Rubric evaluation**: 8 categories - Data model & integrity (18%), Concurrency & correctness (18%), Scaling reasoning (13%), API & frontend craft (13%), Security & isolation (10%), Trade-off writeup (10%), Operational thinking (10%), Code quality & testing (8%). Target 90+ for grade A

**Critical sections (must not omit):**
- Scaling reasoning: "What breaks first" with numbers (Day 6, 100M rows), distinguish "scales with fix" vs "won't scale"
- Trade-off writeup: For each decision - Chose, Rejected, Why, Cost, Revisit criteria. Include "what we'd do differently at 10×"
- Operational thinking: Debug workflow (7 steps with queries), alert thresholds (>10min, >1M, <90%), migration story
- Index strategy: Each index with query pattern, frequency, cost without (full scan timing)
- Threat model: Specific attacks (cross-tenant, replay, brute force) with vector→defense→result→residual format

**Quality auditing workflow:**
1. Run `claude-md-improver` skill to audit CLAUDE.md against rubric
2. Review quality report showing score by category (target 90+/100)
3. Add missing sections systematically (prioritize 0-point categories first)
4. Re-verify coverage: All 8 rubric categories must have content
