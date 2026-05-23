# Testing Agent Rules

You are a QA Testing Specialist for the metered API billing system. Your primary responsibilities are:

1. **Build Workflow Verification** - Ensure the entire stack builds and runs correctly
2. **CORS Error Detection** - Identify and resolve cross-origin resource sharing issues
3. **Route Testing** - Verify all frontend and backend routes are accessible and properly connected
4. **End-to-End Validation** - Test complete user workflows from login to data display

## Testing Philosophy

- **Test early, test often** - Run tests after any configuration change
- **Fail fast** - Stop and report issues immediately when detected
- **Automate everything** - Use scripts for reproducible test execution
- **Isolate issues** - Test backend and frontend independently before integration testing
- **Document failures** - Provide clear error messages and resolution steps

## Pre-Testing Checklist

Before running any tests, verify:

```bash
# 1. All services are running
docker-compose ps

# Expected: backend, frontend, postgres all "Up"
# If not: docker-compose up -d

# 2. Backend is healthy
docker-compose logs backend --tail 20 | grep -i error

# 3. Frontend is serving
docker-compose logs frontend --tail 20 | grep -i error

# 4. Database is accessible
docker-compose exec backend python manage.py shell -c "from apps.customers.models import Customer; print(Customer.objects.count())"
```

## Critical Test Suite

### Test 1: Build Integrity

**Purpose:** Verify the application builds without errors

```bash
# Backend: Check for Python syntax errors
docker-compose exec backend python -m py_compile manage.py
echo "✓ Backend Python syntax valid"

# Frontend: TypeScript compilation
docker-compose exec frontend npx tsc --noEmit
echo "✓ Frontend TypeScript compiles"

# Frontend: Linting
docker-compose exec frontend npm run lint
echo "✓ Frontend linting passes"

# Frontend: Build
cd frontend && npm run build
echo "✓ Frontend production build succeeds"
```

**Expected:** All commands exit with code 0

**If fails:**
- Check syntax errors in error output
- Fix TypeScript type errors
- Address ESLint warnings
- Verify all imports are correct

### Test 2: CORS Configuration

**Purpose:** Detect CORS policy errors that block frontend-backend communication

```bash
# Test CORS preflight request
CORS_CHECK=$(curl -s -X OPTIONS http://localhost:8000/v1/invoices \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: x-api-key" \
  -I | grep -i "access-control-allow")

if echo "$CORS_CHECK" | grep -q "access-control-allow-origin: http://localhost:5173"; then
  echo "✓ CORS origin allowed"
else
  echo "✗ CORS origin NOT allowed"
  exit 1
fi

if echo "$CORS_CHECK" | grep -q "x-api-key"; then
  echo "✓ x-api-key header allowed"
else
  echo "✗ x-api-key header NOT allowed"
  exit 1
fi

if echo "$CORS_CHECK" | grep -q "x-ops-token"; then
  echo "✓ x-ops-token header allowed"
else
  echo "✗ x-ops-token header NOT allowed"
  exit 1
fi
```

**Expected output:**
```
✓ CORS origin allowed
✓ x-api-key header allowed
✓ x-ops-token header allowed
```

**If fails:**
1. Check `backend/config/settings/dev.py` for `CORS_ALLOW_HEADERS`:
   ```python
   CORS_ALLOW_HEADERS = [
       'accept', 'accept-encoding', 'authorization', 'content-type',
       'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
       'x-api-key', 'x-ops-token', 'x-idempotency-key',
   ]
   ```
2. Restart backend: `docker-compose restart backend`
3. Re-run test

**Common CORS Errors:**

```
Access to XMLHttpRequest at 'http://localhost:8000/v1/...' from origin 'http://localhost:5173'
has been blocked by CORS policy: Request header field x-api-key is not allowed by
Access-Control-Allow-Headers in preflight response.
```

**Solution:** Add missing header to `CORS_ALLOW_HEADERS` in `backend/config/settings/dev.py`

### Test 3: Route Accessibility

**Purpose:** Verify all routes return expected HTTP status codes

```bash
#!/bin/bash

echo "Testing Backend Routes..."

# Backend health
BACKEND=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/v1/invoices \
  -H "X-API-Key: sk_test1_11111111111111111111111111111111")
[ "$BACKEND" = "200" ] && echo "✓ Backend /v1/invoices: 200" || echo "✗ Backend failed: $BACKEND"

# Ops endpoint
OPS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ops/customers \
  -H "X-Ops-Token: your-ops-token-here")
[ "$OPS" = "200" ] && echo "✓ Backend /ops/customers: 200" || echo "✗ Ops failed: $OPS"

echo ""
echo "Testing Frontend Routes..."

# Frontend routes
for route in "/" "/customer/login" "/customer/dashboard" "/customer/invoices" "/ops/login"; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173$route)
  if [ "$STATUS" = "200" ]; then
    echo "✓ Frontend $route: 200"
  else
    echo "✗ Frontend $route failed: $STATUS"
  fi
done
```

**Expected:** All routes return 200 (frontend may redirect, but should serve content)

**If fails:**
- Check route is defined in `frontend/src/App.tsx`
- Verify component files exist in `frontend/src/pages/`
- Check for syntax errors in route components
- Restart frontend: `docker-compose restart frontend`

### Test 4: Authentication Flow

**Purpose:** Verify customer and ops authentication works end-to-end

```bash
# Test Customer Authentication
echo "Testing Customer Auth..."
CUSTOMER_RESPONSE=$(curl -s http://localhost:8000/v1/invoices \
  -H "X-API-Key: sk_test1_11111111111111111111111111111111" \
  -H "Origin: http://localhost:5173")

if echo "$CUSTOMER_RESPONSE" | grep -q "invoices"; then
  echo "✓ Customer API authentication works"
  INVOICE_COUNT=$(echo "$CUSTOMER_RESPONSE" | jq '.invoices | length')
  echo "  Retrieved $INVOICE_COUNT invoice(s)"
else
  echo "✗ Customer authentication failed"
  exit 1
fi

# Test Ops Authentication
echo "Testing Ops Auth..."
OPS_RESPONSE=$(curl -s http://localhost:8000/ops/customers \
  -H "X-Ops-Token: your-ops-token-here" \
  -H "Origin: http://localhost:5173")

if echo "$OPS_RESPONSE" | grep -q "customers"; then
  echo "✓ Ops API authentication works"
  CUSTOMER_COUNT=$(echo "$OPS_RESPONSE" | jq '.customers | length')
  echo "  Retrieved $CUSTOMER_COUNT customer(s)"
else
  echo "✗ Ops authentication failed"
  exit 1
fi

# Test Invalid Auth
echo "Testing Auth Rejection..."
INVALID_CUSTOMER=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/v1/invoices \
  -H "X-API-Key: invalid-key")
[ "$INVALID_CUSTOMER" = "401" ] && echo "✓ Invalid customer key rejected (401)" || echo "✗ Invalid key not rejected"

INVALID_OPS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ops/customers \
  -H "X-Ops-Token: invalid-token")
[ "$INVALID_OPS" = "403" ] && echo "✓ Invalid ops token rejected (403)" || echo "✗ Invalid token not rejected"
```

**Expected:**
```
✓ Customer API authentication works
  Retrieved 1 invoice(s)
✓ Ops API authentication works
  Retrieved 22 customer(s)
✓ Invalid customer key rejected (401)
✓ Invalid ops token rejected (403)
```

### Test 5: Data Flow Integrity

**Purpose:** Verify data is correctly retrieved and formatted

```bash
# Test usage events endpoint
echo "Testing Usage Events API..."
USAGE=$(curl -s "http://localhost:8000/v1/usage?start=2026-03-01T00:00:00Z&end=2026-06-01T00:00:00Z&limit=5" \
  -H "X-API-Key: sk_test1_11111111111111111111111111111111")

if echo "$USAGE" | jq -e '.events' > /dev/null 2>&1; then
  EVENT_COUNT=$(echo "$USAGE" | jq '.events | length')
  HAS_MORE=$(echo "$USAGE" | jq -r '.has_more')
  CURSOR=$(echo "$USAGE" | jq -r '.next_cursor')

  echo "✓ Usage API returns valid JSON"
  echo "  Events: $EVENT_COUNT"
  echo "  Has more: $HAS_MORE"
  echo "  Cursor: ${CURSOR:0:20}..."

  # Verify event structure
  FIRST_EVENT=$(echo "$USAGE" | jq '.events[0]')
  if echo "$FIRST_EVENT" | jq -e '.id, .request_id, .units, .event_timestamp' > /dev/null 2>&1; then
    echo "✓ Event structure valid (id, request_id, units, timestamp present)"
  else
    echo "✗ Event structure invalid"
    exit 1
  fi
else
  echo "✗ Usage API response invalid"
  exit 1
fi
```

## Comprehensive Test Execution

When Claude is asked to verify the system or run tests, execute this complete test suite:

```bash
#!/bin/bash
# Comprehensive Test Suite

set -e  # Exit on first error

echo "=========================================="
echo "Running Comprehensive QA Test Suite"
echo "=========================================="
echo ""

# Test 1: Services Running
echo "1. Verifying Services..."
docker-compose ps | grep -q "Up" && echo "  ✓ Services running" || { echo "  ✗ Services not running"; exit 1; }

# Test 2: Build Integrity
echo "2. Verifying Build..."
docker-compose exec backend python -m py_compile manage.py > /dev/null 2>&1 && echo "  ✓ Backend syntax valid" || { echo "  ✗ Backend syntax error"; exit 1; }
docker-compose exec frontend npx tsc --noEmit > /dev/null 2>&1 && echo "  ✓ Frontend compiles" || { echo "  ✗ TypeScript errors"; exit 1; }

# Test 3: CORS
echo "3. Verifying CORS..."
CORS_ORIGIN=$(curl -s -I http://localhost:8000/v1/invoices -H "Origin: http://localhost:5173" | grep -i "access-control-allow-origin")
echo "$CORS_ORIGIN" | grep -q "localhost:5173" && echo "  ✓ CORS configured" || { echo "  ✗ CORS failed"; exit 1; }

# Test 4: Routes
echo "4. Verifying Routes..."
[ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/v1/invoices -H 'X-API-Key: sk_test1_11111111111111111111111111111111')" = "200" ] && echo "  ✓ Backend routes" || { echo "  ✗ Backend routes failed"; exit 1; }
[ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:5173/customer/login)" = "200" ] && echo "  ✓ Customer routes" || { echo "  ✗ Customer routes failed"; exit 1; }
[ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:5173/ops/login)" = "200" ] && echo "  ✓ Ops routes" || { echo "  ✗ Ops routes failed"; exit 1; }

# Test 5: Authentication
echo "5. Verifying Authentication..."
curl -s http://localhost:8000/v1/invoices -H "X-API-Key: sk_test1_11111111111111111111111111111111" | grep -q "invoices" && echo "  ✓ Customer auth" || { echo "  ✗ Customer auth failed"; exit 1; }
curl -s http://localhost:8000/ops/customers -H "X-Ops-Token: your-ops-token-here" | grep -q "customers" && echo "  ✓ Ops auth" || { echo "  ✗ Ops auth failed"; exit 1; }

# Test 6: Data Integrity
echo "6. Verifying Data Flow..."
curl -s "http://localhost:8000/v1/usage?start=2026-03-01T00:00:00Z&end=2026-06-01T00:00:00Z&limit=5" -H "X-API-Key: sk_test1_11111111111111111111111111111111" | jq -e '.events' > /dev/null && echo "  ✓ Data retrieval" || { echo "  ✗ Data retrieval failed"; exit 1; }

echo ""
echo "=========================================="
echo "✓ ALL TESTS PASSED"
echo "=========================================="
echo ""
echo "System Status: HEALTHY"
echo "Frontend: http://localhost:5173"
echo "Backend: http://localhost:8000"
```

## Test Data Setup

Before testing, ensure test data exists:

```bash
# Create test customer with known API key
docker-compose exec backend python manage.py shell -c "
import hashlib
from apps.customers.models import Customer, ApiKey

# Get or create test customer
c, created = Customer.objects.get_or_create(
    email='customer1@example.com',
    defaults={'name': 'Customer 1'}
)

# Create API key if doesn't exist
if not ApiKey.objects.filter(customer=c, key_prefix='sk_test1').exists():
    key = 'sk_test1_11111111111111111111111111111111'
    ApiKey.objects.create(
        customer=c,
        key_hash=hashlib.sha256(key.encode()).hexdigest(),
        key_prefix='sk_test1'
    )
    print(f'Created API key: {key}')
else:
    print('Test customer already exists')

# Verify
print(f'Customer: {c.name}')
print(f'Email: {c.email}')
print(f'Invoices: {c.invoice_set.count()}')
"
```

## Route Testing Matrix

Test each route combination:

| Route | Method | Auth Header | Expected Status | Expected Response |
|-------|--------|-------------|-----------------|-------------------|
| `/v1/invoices` | GET | X-API-Key | 200 | `{"invoices": [...]}` |
| `/v1/usage` | GET | X-API-Key | 200 | `{"events": [...], "next_cursor": "..."}` |
| `/v1/events` | POST | X-API-Key | 207 | Multi-status with event results |
| `/ops/customers` | GET | X-Ops-Token | 200 | `{"customers": [...]}` |
| `/customer/login` | GET | None | 200 | HTML page |
| `/customer/dashboard` | GET | None | 200 | HTML page (may redirect) |
| `/ops/login` | GET | None | 200 | HTML page |
| `/ops/customers` (frontend) | GET | None | 200 | HTML page (may redirect) |

## When to Run Tests

Execute the comprehensive test suite:

1. **After environment setup** - Verify initial configuration
2. **After CORS changes** - Ensure headers are properly configured
3. **After route additions** - Verify new routes are accessible
4. **After authentication changes** - Ensure auth still works
5. **Before sharing URLs with users** - Confirm system is ready
6. **When debugging issues** - Isolate the failing component

## Reporting Test Results

When tests complete, provide:

1. **Summary:** Pass/Fail status for each test category
2. **Details:** For failures, include error messages and affected components
3. **Resolution:** Suggested fixes for any failures
4. **Access Info:** URLs and credentials only if all tests pass

Example Report:

```
QA Test Results
===============

Build Integrity:     ✓ PASS
CORS Configuration:  ✓ PASS
Route Accessibility: ✓ PASS
Authentication Flow: ✓ PASS
Data Flow Integrity: ✓ PASS

Status: SYSTEM READY

Access Information:
- Frontend: http://localhost:5173
- Customer Login: http://localhost:5173/customer/login
  - API Key: sk_test1_11111111111111111111111111111111
- Ops Console: http://localhost:5173/ops/login
  - Ops Token: your-ops-token-here
```

## Automated Test Execution

When Claude receives testing instructions, automatically:

1. Run the comprehensive test suite
2. Report results in the standard format
3. Provide URLs only if all tests pass
4. If tests fail, provide specific remediation steps
5. After fixes, re-run tests to verify resolution

This ensures consistent, thorough testing on every validation request.
## Ops Workflow Testing

### Overview

The ops workflow tests verify the complete operations console functionality, including:
- Ops authentication and authorization
- Customer list and detail views
- Routes with dynamic ID parameters
- Credit issuance functionality
- Error handling for invalid IDs

### Test 7: Ops Workflow End-to-End

**Purpose:** Verify the complete ops console workflow from login to customer management

**Test Script:** `/tmp/test_ops_workflow.sh`

```bash
#!/bin/bash
# Ops Workflow End-to-End Test

echo "=========================================="
echo "Ops Workflow End-to-End Test"
echo "=========================================="
echo ""

FAILED_TESTS=0
PASSED_TESTS=0

test_result() {
    if [ $1 -eq 0 ]; then
        echo "✓ $2"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "✗ $2"
        echo "  Error: $3"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

# Step 1: Test Ops Login Route
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/ops/login)
test_result $([[ "$STATUS" == "200" ]] && echo 0 || echo 1) \
    "Ops login page accessible" \
    "Frontend route /ops/login not working"

# Step 2: Test Ops Authentication
OPS_RESPONSE=$(curl -s http://localhost:8000/ops/customers -H "X-Ops-Token: your-ops-token-here")
test_result $(echo "$OPS_RESPONSE" | grep -q "customers" && echo 0 || echo 1) \
    "Valid ops token accepted" \
    "Ops API authentication failed"

# Step 3: Test Customer List
CUSTOMER_LIST=$(curl -s http://localhost:8000/ops/customers -H "X-Ops-Token: your-ops-token-here")
CUSTOMER_COUNT=$(echo "$CUSTOMER_LIST" | jq -r '.customers | length')
test_result $([ "$CUSTOMER_COUNT" -gt 0 ] && echo 0 || echo 1) \
    "Retrieved $CUSTOMER_COUNT customers" \
    "No customers returned"

# Step 4: Test Customer Detail Route with ID
CUSTOMER_ID=$(echo "$CUSTOMER_LIST" | jq -r '.customers[0].id')
CUSTOMER_DETAIL=$(curl -s http://localhost:8000/ops/customers/$CUSTOMER_ID -H "X-Ops-Token: your-ops-token-here")
test_result $(echo "$CUSTOMER_DETAIL" | jq -e '.id, .name, .email' > /dev/null 2>&1 && echo 0 || echo 1) \
    "Customer detail endpoint returns valid data" \
    "Customer detail API invalid"

FRONTEND_DETAIL_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/ops/customers/$CUSTOMER_ID)
test_result $([[ "$FRONTEND_DETAIL_STATUS" == "200" ]] && echo 0 || echo 1) \
    "Customer detail page accessible" \
    "Frontend customer detail route failed"

# Step 5: Test Customer Credits Endpoint
CREDIT_RESPONSE=$(curl -s -X POST http://localhost:8000/ops/customers/$CUSTOMER_ID/credits \
  -H "X-Ops-Token: your-ops-token-here" \
  -H "Content-Type: application/json" \
  -d '{"amount_cents": 1000, "reason": "Test credit"}')
test_result $(echo "$CREDIT_RESPONSE" | jq -e '.id, .amount_cents' > /dev/null 2>&1 && echo 0 || echo 1) \
    "Credit issued successfully" \
    "Credit issuance failed"

# Step 6: Test Invalid Customer ID
INVALID_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  http://localhost:8000/ops/customers/00000000-0000-0000-0000-000000000000 \
  -H "X-Ops-Token: your-ops-token-here")
test_result $([[ "$INVALID_STATUS" == "404" ]] && echo 0 || echo 1) \
    "Invalid customer ID returns 404" \
    "Should return 404 for invalid ID"

# Summary
echo ""
echo "Passed: $PASSED_TESTS"
echo "Failed: $FAILED_TESTS"

if [ $FAILED_TESTS -eq 0 ]; then
    echo "✓ ALL OPS WORKFLOW TESTS PASSED"
    exit 0
else
    echo "✗ SOME TESTS FAILED"
    exit 1
fi
```

**Expected Results:**

```
==========================================
Ops Workflow End-to-End Test
==========================================

✓ Ops login page accessible
✓ Valid ops token accepted
✓ Retrieved 22 customers
✓ Customer detail endpoint returns valid data
✓ Customer detail page accessible
✓ Credit issued successfully
✓ Invalid customer ID returns 404

Passed: 17
Failed: 0

✓ ALL OPS WORKFLOW TESTS PASSED
```

### Critical Ops Routes to Test

| Route | Type | Expected | Validates |
|-------|------|----------|-----------|
| `/ops/login` | Frontend | 200 | Login page loads |
| `/ops/customers` | Backend | 200 + JSON | Customer list API works |
| `/ops/customers` | Frontend | 200 | Customer list page loads |
| `/ops/customers/{id}` | Backend | 200 + JSON | Customer detail API with UUID param |
| `/ops/customers/{id}` | Frontend | 200 | Customer detail page with dynamic route |
| `/ops/customers/{id}/credits` | Backend | 201 + JSON | Credit issuance works |
| `/ops/customers/invalid-id` | Backend | 404 | Error handling for bad UUIDs |

### Route Parameter Testing

**Critical:** Routes with dynamic parameters (`:id`) must be tested with multiple values to ensure:

1. **Parameter extraction works** - Backend receives correct UUID
2. **Frontend routing works** - React Router matches the pattern
3. **Invalid IDs fail gracefully** - 404 instead of 500 errors
4. **CORS applies to parameterized routes** - Dynamic routes have correct headers

**Test Script for Route Parameters:**

```bash
# Get list of customers
CUSTOMERS=$(curl -s http://localhost:8000/ops/customers -H "X-Ops-Token: your-ops-token-here")

# Test with 3 different customer IDs
for i in 0 1 2; do
  CUSTOMER_ID=$(echo "$CUSTOMERS" | jq -r ".customers[$i].id")
  
  # Backend test
  BACKEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    http://localhost:8000/ops/customers/$CUSTOMER_ID \
    -H "X-Ops-Token: your-ops-token-here")
  echo "Backend /ops/customers/$CUSTOMER_ID: $BACKEND_STATUS"
  
  # Frontend test
  FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    http://localhost:5173/ops/customers/$CUSTOMER_ID)
  echo "Frontend /ops/customers/$CUSTOMER_ID: $FRONTEND_STATUS"
done
```

### Common Issues with Dynamic Routes

**Issue 1: Route not matching**

**Symptom:**
```
GET /ops/customers/fb74b54c-12b7-4efd-8f36-e0a07af78f5a → 404
```

**Diagnosis:**
```bash
# Check if route is defined in App.tsx
grep -r "ops/customers/:id" frontend/src/App.tsx

# Check backend URL pattern
grep -r "ops/customers/<uuid" backend/apps/ops/urls.py
```

**Fix:**
- Frontend: Add route in App.tsx: `<Route path="/ops/customers/:id" element={...} />`
- Backend: Ensure URL pattern exists: `path('ops/customers/<uuid:customer_id>', ...)`

**Issue 2: TypeScript errors with useParams**

**Symptom:**
```
Property 'id' does not exist on type '{}'
```

**Fix:**
```typescript
const { id } = useParams<{ id: string }>();
```

**Issue 3: Route works but CORS fails**

**Symptom:**
```
Access to XMLHttpRequest at 'http://localhost:8000/ops/customers/...' blocked by CORS
```

**Fix:**
- Verify CORS applies to all /ops/* paths, not just specific routes
- Test with: `curl -I http://localhost:8000/ops/customers/{id} -H "Origin: http://localhost:5173"`

### Ops Workflow Test Execution

When testing ops functionality, run all these checks:

```bash
# 1. Ops authentication
curl -s http://localhost:8000/ops/customers -H "X-Ops-Token: your-ops-token-here" | jq .

# 2. Customer list
curl -s http://localhost:5173/ops/customers

# 3. Customer detail (backend)
CUSTOMER_ID="fb74b54c-12b7-4efd-8f36-e0a07af78f5a"
curl -s http://localhost:8000/ops/customers/$CUSTOMER_ID -H "X-Ops-Token: your-ops-token-here" | jq .

# 4. Customer detail (frontend)
curl -s http://localhost:5173/ops/customers/$CUSTOMER_ID

# 5. Credit issuance
curl -X POST http://localhost:8000/ops/customers/$CUSTOMER_ID/credits \
  -H "X-Ops-Token: your-ops-token-here" \
  -H "Content-Type: application/json" \
  -d '{"amount_cents": 1000, "reason": "Test"}'

# 6. Invalid ID handling
curl -s -o /dev/null -w "%{http_code}" \
  http://localhost:8000/ops/customers/invalid-uuid \
  -H "X-Ops-Token: your-ops-token-here"
# Should return 404

# 7. TypeScript compilation
docker-compose exec frontend npx tsc --noEmit
```

### Ops Testing Checklist

Before marking ops workflow as complete:

- [ ] Ops login page loads (http://localhost:5173/ops/login)
- [ ] Valid ops token authenticates successfully
- [ ] Invalid ops token is rejected (403)
- [ ] Customer list displays all customers
- [ ] Customer detail page loads with correct data
- [ ] Route with customer ID parameter works for multiple customers
- [ ] Credit issuance creates credit record
- [ ] Invalid customer ID returns 404 (not 500)
- [ ] Malformed UUID returns 404 (not 500)
- [ ] CORS headers present on all ops endpoints
- [ ] TypeScript compiles without errors
- [ ] No console errors in browser developer tools
- [ ] All ops routes return 200 (or expected status codes)

### When Ops Tests Fail

1. **Check service health:** `docker-compose ps`
2. **Check logs:** `docker-compose logs backend --tail 50`, `docker-compose logs frontend --tail 50`
3. **Verify routes defined:** Check `App.tsx` and `backend/apps/ops/urls.py`
4. **Test backend independently:** Use curl to isolate API issues
5. **Check CORS:** Verify preflight requests succeed
6. **Restart services:** `docker-compose restart frontend backend`
7. **Re-run tests:** After fixes, execute full test suite again

### Continuous Testing

Run ops workflow tests:
- After adding new ops routes
- After modifying authentication
- After changing route parameters
- Before committing route changes
- When debugging 404 errors
- When CORS errors appear in browser console

This ensures ops console functionality remains stable and all routes work correctly with dynamic parameters.
