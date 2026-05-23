Write DESIGN.md for this metered API billing system. Target 1,800–2,200 words. Be specific and honest. Cover these 7 sections:

1. Data Model
   - Describe the schema and key relationships
   - Explain why request_id has a UNIQUE index (idempotency)
   - Explain cursor-based pagination choice over offset for usage events
   - What indexes would you add at 10× (partial indexes on unprocessed events) and 100× (partitioning UsageEvent by month)

2. Idempotency & Concurrency
   - Event ingestion: INSERT ON CONFLICT DO NOTHING
   - Aggregator: INSERT ON CONFLICT DO UPDATE + SELECT FOR UPDATE SKIP LOCKED job lock
   - Webhook: WebhookDelivery dedup table
   - Ops credit: SELECT FOR UPDATE on customer row to prevent race
   - "Issue credit" button: client-generated idempotency token prevents double-submit

3. Aggregation Pipeline
   - Events → hourly UsageWindows → monthly InvoiceLineItems
   - What's recomputable (windows from raw events) vs immutable (issued invoices)
   - Late-arriving events: if window not yet finalized, re-aggregate; if invoice already issued, create an adjustment line item in the next invoice period — describe this explicitly

4. Failure Modes (pick 3)
   - Aggregator backlog under sustained 2000/sec peak
   - Clock skew causing events to land in wrong window
   - Invoice generation crash mid-run leaving partial invoices

5. Threat Model
   - Hostile customer: cross-tenant access attempt (stopped by dependency-layer tenant scoping), API key brute force (stopped by hashing + rate limiting), invoice ID enumeration (UUIDs + tenant scope)
   - Hostile internal user: ops issuing fraudulent credits (stopped by immutable audit log with before/after, reason required), overriding line items (audit trail)
   - Compromised webhook source: replay attack (WebhookDelivery dedup), forged payload (HMAC-SHA256 signature verification)

6. Trade-offs (pick 2 non-obvious ones)
   - Cursor vs offset pagination: chose cursor for stable results under concurrent writes; rejected offset because page drift makes billing debugging harder
   - Hourly windows vs per-event aggregation: chose hourly for predictable query cost; rejected real-time aggregation as premature at this scale

7. What you didn't build and would build next
   - Be honest: real-time usage alerts, proration for mid-month plan changes, dunning/retry logic for failed payments, distributed tracing

Write in plain technical prose. No fluff. Be specific about numbers and mechanisms.
