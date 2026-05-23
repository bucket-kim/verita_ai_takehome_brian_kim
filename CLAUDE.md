# CLAUDE.md

Metered API billing system with Django REST Framework backend and React frontend.

## Key Conventions

- **Django models**: Use string references for cross-app ForeignKeys (e.g., `"customers.Customer"`)
- **Money handling**: IntegerField (cents), millicents for pricing - no floats
- **Immutable models**: Override save/delete to raise PermissionError (e.g., AuditLog)

## Directory Structure

- `backend/apps/` - Django apps: `billing` (invoices, line items), `customers` (Customer, ApiKey), `ops` (admin endpoints, JobLock), `usage` (events, aggregated windows)
- `frontend/src/` - React app: `api/` (axios client), `hooks/` (data fetching), `pages/` (routes), `components/` (shared UI), `types/` (TypeScript interfaces)

## API Architecture Patterns

- **URL structure**: Customer endpoints at `/v1/*`, ops at `/ops/*`, webhooks at `/webhooks/*` (all mounted at root in config/urls.py)
- **Authentication**: ApiKeyAuthentication (X-API-Key header, SHA256 hash lookup) for /v1, OpsTokenAuthentication (X-Ops-Token header) for /ops, HMAC signature verification for webhooks
- **Tenant scoping**: TenantScopedAPIView base class sets `self.customer = request.user` in initial() - extend for all /v1 views
- **Cursor pagination**: Base64-encoded `timestamp|id` format for stateless pagination across large datasets
- **Idempotency**: bulk_create(ignore_conflicts=True) for events, get_or_create() for webhook deliveries
- **Events API format**: POST /v1/events accepts `{"events": [{request_id, api_key_id, endpoint, units, timestamp}]}` bulk format, returns 207 Multi-Status
- **Concurrency safety**: select_for_update() when modifying customer balances/credits, transaction.atomic() for multi-step updates
- **Security**: hmac.compare_digest() for constant-time comparison (webhook signatures, tokens)
- **Audit logging**: Create AuditLog entries for sensitive ops actions with before_value/after_value

## Background Jobs and Pricing

- **Job locking**: Use select_for_update(skip_locked=True) on JobLock model to prevent concurrent execution
- **APScheduler setup**: Check `os.environ.get('RUN_MAIN') == 'true'` in apps.py ready() to avoid duplicate scheduler in Django reloader
- **Tiered pricing**: All arithmetic in millicents (integer), convert to cents only at Invoice.total_cents
- **aggregate_usage_windows**: Runs every 5min, uses TruncHour() to group events by customer+hour
- **generate_invoices**: Runs 1st of month at midnight, applies 3-tier pricing (0/100/50 millicents)

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

- Run all frontend checks: `cd frontend && npm run lint && npx tsc --noEmit && npm run build`
- Run backend tests: `docker-compose exec backend pytest`
- Run specific test: `docker-compose exec backend pytest tests/test_name.py -v`
- Run tests with details: `docker-compose exec backend pytest tests/ -v --tb=long`
- Run makemigrations: `docker-compose exec backend python manage.py makemigrations customers usage billing ops`
- Run database migrations: `docker-compose exec backend python manage.py migrate`

**Note:** Backend service must be running for `docker-compose exec` commands

## Testing Patterns

- **pytest fixtures**: Define shared test data in conftest.py (customers, API keys, tokens)
- **Threading tests**: Use `@pytest.mark.django_db(transaction=True)` for concurrent tests
- **Webhook tests**: Use `api_client.generic()` for exact request body control (signature verification)
- **EventsView format**: POST to `/v1/events` with `{"events": [...]}` bulk format, returns 207 status
- **Idempotency testing**: Test same operation from multiple threads with same idempotency key

## Common Patterns

- **Customer as user object**: Customer model needs `is_authenticated` property for DRF's IsAuthenticated permission
- **Management commands**: Create in `apps/<app>/management/commands/<name>.py` with `__init__.py` files in parent dirs
- **Month arithmetic**: Avoid external deps - use manual month/year calculation instead of dateutil.relativedelta
- **AuditLog entity_id queries**: Convert integer IDs to strings before filtering (entity_id is CharField, not IntegerField)

## Frontend Development

- **TypeScript imports**: Use `import type { ... }` for type-only imports (verbatimModuleSyntax enabled)
- **React Router v7**: Import from `react-router` package (BrowserRouter, Routes, Route, Link, useNavigate, useParams)
- **Directory structure**: `src/{api,hooks,pages,components,types}` - follow this pattern
- **Protected routes**: Check `localStorage.getItem('apiKey')`, redirect to `/customer/login` if missing
- **Recharts**: Wrap charts in ResponsiveContainer, use AreaChart for time series
- **Data fetching hooks**: Wrap fetch functions in useCallback, disable `react-hooks/set-state-in-effect` rule for initial data fetch in useEffect
- **Frontend dev server**: `npm run dev` starts Vite at localhost:5173, auto-reloads on changes
- **Testing UI**: Use sample API key from `python manage.py seed` output
- **Vite in Docker**: Add `server: { host: '0.0.0.0', port: 5173 }` to vite.config.ts for external access
- **CORS headers**: Custom headers (`x-api-key`, `x-ops-token`, `x-idempotency-key`) must be in CORS_ALLOW_HEADERS in dev.py
- **Frontend restart**: Run `docker-compose restart frontend` after adding new pages/components for proper loading
