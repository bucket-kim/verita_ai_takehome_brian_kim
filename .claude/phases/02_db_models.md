In the Django backend, create models across the four apps for a metered API billing system.

apps/customers/models.py:

- Customer: id (UUIDField, primary_key), name, email (unique), created_at
- ApiKey: id (UUIDField), customer (FK to Customer, on_delete=PROTECT),
  key_hash (CharField, sha256 — never store plaintext),
  key_prefix (CharField, first 8 chars for display only),
  created_at, revoked_at (nullable)

apps/usage/models.py:

- UsageEvent: id (UUIDField), request_id (CharField, unique=True — idempotency key),
  customer (FK), api_key (FK to ApiKey), endpoint (CharField),
  units (PositiveIntegerField), event_timestamp, ingested_at (auto_now_add)
- UsageWindow: id, customer (FK), window_start (DateTimeField, hourly boundary),
  window_end, total_units (PositiveIntegerField), finalized (BooleanField, default=False)
  Meta: unique_together = [('customer', 'window_start')]

apps/billing/models.py:

- PricePlan: id, name, tiers (JSONField)
  e.g. [{"up_to": 10000, "unit_price_millicents": 0}, {"up_to": 100000, "unit_price_millicents": 100}, {"up_to": null, "unit_price_millicents": 50}]
  Note: store prices as integer millicents (1/1000 of a cent) to avoid floats
- Invoice: id (UUIDField), customer (FK), period_start, period_end,
  status (CharField, choices: draft/issued/paid), total_cents (IntegerField),
  created_at, paid_at (nullable)
- InvoiceLineItem: id, invoice (FK, related_name='line_items'), description,
  units (IntegerField), unit_price_millicents (IntegerField), total_cents (IntegerField),
  overridden (BooleanField, default=False)
- Credit: id, customer (FK), amount_cents (IntegerField), reason, created_at, created_by

apps/ops/models.py:

- AuditLog: id, entity_type, entity_id, action, actor,
  before_value (JSONField), after_value (JSONField), reason, created_at (auto_now_add)
  — Override save() and delete() to raise PermissionError so no code path can mutate rows
- WebhookDelivery: id, external_id (CharField, unique=True), payload (JSONField), processed_at

Add indexes via Meta class:

- UsageEvent: index on (customer, event_timestamp), unique on request_id
- UsageWindow: index on (customer, window_start)
- Invoice: index on (customer, status)

Run makemigrations for all four apps.
