Write pytest tests for the backend covering these correctness boundaries only (not trivial coverage):

1. Idempotency — POST /v1/events with same request_id twice: assert only 1 row in UsageEvent table
2. Concurrent ingestion — use threading to POST the same request_id from 10 concurrent threads: assert exactly 1 row
3. Tenant isolation — Customer A cannot access Customer B's invoice by guessing the UUID (GET /v1/invoices/{b_invoice_id} with A's API key returns 404, not 403)
4. Aggregation idempotency — run aggregate_usage_windows() twice on same data: assert UsageWindow totals are unchanged
5. Webhook replay — POST /webhooks/payments with same external_id twice: assert invoice status updated only once, only 1 WebhookDelivery row
6. Double credit prevention — simulate two concurrent POST /ops/customers/{id}/credits requests: assert total credits applied equals expected (not doubled)
7. Tiered pricing correctness — generate invoice for customer with exactly 150,000 units: assert line items sum to correct cents (10k free + 90k × 0.1 cents + 50k × 0.05 cents)
8. Audit log immutability — attempt to UPDATE or DELETE an AuditLog row directly via SQLAlchemy session: assert it raises an exception or the DB trigger prevents it

Use pytest-asyncio for async tests. Use a separate test database (TEST_DATABASE_URL env var).
