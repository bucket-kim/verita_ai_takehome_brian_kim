Implement API endpoints using Django REST Framework.

AUTHENTICATION — create apps/customers/authentication.py:

- ApiKeyAuthentication(BaseAuthentication):
  reads X-API-Key header, hashes it with sha256, looks up ApiKey by key_hash
  where revoked_at is null. Returns (api_key.customer, api_key).
  Never return the plaintext key anywhere.
- Register as DEFAULT_AUTHENTICATION_CLASSES in settings.
- Tenant scoping: create a TenantScopedAPIView(APIView) base class that sets
  self.customer = request.user (the resolved Customer) in initial().
  All /v1 views must extend this — scoping must NOT be repeated per view.

OPS AUTHENTICATION — create apps/ops/authentication.py:

- OpsTokenAuthentication(BaseAuthentication):
  reads X-Ops-Token header, compares (using hmac.compare_digest) against
  OPS_TOKEN env var. Returns a simple internal user object.

Customer-facing views (apps/usage/views.py and apps/billing/views.py):

1. POST /v1/events
   - Accept: {"events": [{request_id, api_key_id, endpoint, units, timestamp}]}
   - Bulk insert using UsageEvent.objects.bulk_create(ignore_conflicts=True)
   - ignore_conflicts=True handles the unique request_id idempotency
   - Return 207 with per-event {"request_id": ..., "status": "created"|"duplicate"}

2. GET /v1/usage?start=&end=&api_key_id=&cursor=&limit=50
   - Filter UsageEvent by self.customer, date range, optional api_key_id
   - Cursor pagination: cursor = base64-encoded last (event_timestamp, id)
   - Always filter by self.customer first

3. GET /v1/invoices — list invoices for self.customer only
4. GET /v1/invoices/<uuid:id> — get invoice + line_items.
   Use get_object_or_404(Invoice, id=id, customer=self.customer) —
   the customer filter is what prevents cross-tenant access.

Ops-facing views (apps/ops/views.py):

5. GET /ops/customers?cursor=&limit=50
6. GET /ops/customers/<uuid:id>
7. POST /ops/customers/<uuid:id>/credits
   - Wrap in transaction.atomic()
   - Use select_for_update() on Customer row to prevent concurrent double-credit
   - Create Credit, write AuditLog entry with actor from request, before/after values
8. PATCH /ops/invoices/<uuid:id>/line-items/<uuid:lid>
   - Body: {total_cents, reason}
   - Write AuditLog with before_value (old total_cents), after_value (new total_cents), reason

9. POST /webhooks/payments
   - Verify HMAC-SHA256: hmac.new(WEBHOOK_SECRET, body, sha256).hexdigest() vs X-Webhook-Signature
   - Use hmac.compare_digest to prevent timing attacks
   - Idempotency: WebhookDelivery.objects.get_or_create(external_id=...)
     skip processing if already exists
   - On valid new delivery: update Invoice status to 'paid', set paid_at

Wire all URLs in config/urls.py.
