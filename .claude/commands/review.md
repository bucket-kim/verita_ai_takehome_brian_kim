You are wording specialist, who can analyze the workflow and understand what CLAUDE.md file is saying. You are GREAT at summarizing features into 1500 ~ 2500 words. Review DESIGN.md to ensure it addresses all critical design dimensions with specific implementation details. Check for concrete examples, numbers, and trade-off reasoning. If words go over 2500, REVISE and shorten with best of your ability.

# Design Review Checklist

## 1. Data Model & Indexing Strategy

**Required Coverage:**

### Current Schema

- [ ] All tables listed with columns and types
- [ ] Foreign key relationships explicit
- [ ] Database constraints (UNIQUE, CHECK) with business rationale

### Index Justification

Each index must answer:

- **Query:** What specific query uses this index?
- **Frequency:** How often does this query run?
- **Cost without index:** What happens without it (full table scan on X rows)?

**Example standard:**

```
✓ GOOD: "UsageEvent(customer_id, event_timestamp) - aggregator runs every 5min,
queries GROUP BY customer, TruncHour(event_timestamp). Without index: full scan
of 100M+ rows takes >5min, exceeds job interval."

✗ BAD: "Index on customer_id for performance."
```

**Required indexes to verify:**

- UsageEvent(request_id) UNIQUE - why unique vs just indexed?
- UsageEvent(customer_id, event_timestamp) - aggregation query
- UsageWindow(customer_id, window_start) UNIQUE - why unique?
- ApiKey(key_hash) - authentication lookup
- Invoice(customer_id, status) - ops queries

### Scaling Indexes (10× and 100×)

**At 10× (500M events/month → 5B events/month):**

- [ ] Specific new indexes proposed with query patterns
- [ ] Partial indexes for hot data (e.g., `WHERE finalized=false`)
- [ ] Composite index reordering based on query selectivity

**At 100× (500M → 50B events/month):**

- [ ] Partitioning strategy (range by timestamp, hash by customer?)
- [ ] Archive strategy (move to cold storage after N days?)
- [ ] Sharding approach (if needed)

**Check for:**

- Specific numbers (not "at scale" but "at 5B rows")
- Query examples that break without the proposed index
- Storage cost estimates (partial index size vs full table)

---

## 2. Idempotency & Concurrency Safety

**Required Scenarios (must have code examples):**

### Event Ingestion Replay

- [ ] Mechanism: `bulk_create(ignore_conflicts=True)` with UNIQUE(request_id)
- [ ] Database-level enforcement (not just application logic)
- [ ] Concurrent thread safety (race condition analysis)

**Test case required:**

```python
# 10 threads POST same request_id simultaneously
# Result: Exactly 1 UsageEvent created (not 10, not 0)
```

### Aggregator Runs Twice

- [ ] JobLock with `select_for_update(skip_locked=True)`
- [ ] What happens if process crashes mid-aggregation?
- [ ] Are window updates idempotent? (`update_or_create` logic)

**Specific question:** If aggregator processes hour X twice, does window have correct total?

### Webhook Delivered 3 Times

- [ ] UNIQUE(external_id) constraint on WebhookDelivery
- [ ] `get_or_create()` returns existing row on replay
- [ ] Invoice status updated exactly once (not 3 times)

**Specific question:** Can concurrent webhook deliveries create duplicate entries?

### Ops Clicks "Issue Credit" Twice

- [ ] `select_for_update()` locks Customer row
- [ ] Idempotency key from frontend (UUID in header)
- [ ] Credit.objects.create() within transaction

**Check for:**

- Actual code snippets (not just descriptions)
- Database transaction boundaries (`transaction.atomic()`)
- Lock scope (row-level vs table-level)
- Deadlock prevention strategy

---

## 3. Aggregation Pipeline

**Required Flow Diagram:**

```
UsageEvent (raw)
  ↓ [aggregator every 5min]
UsageWindow (hourly buckets)
  ↓ [invoice generator monthly]
InvoiceLineItem (tiered pricing applied)
  ↓
Invoice (sum of line items)
```

### State Management

- [ ] Which data is source of truth? (raw events vs windows)
- [ ] What's recomputable? (windows can be rebuilt from events)
- [ ] What's immutable? (invoices after generation, events always)

### Late Event Handling

**Scenario:** Event with timestamp=Jan 15 arrives on Feb 5 (after Jan invoice generated)

- [ ] Detection: How do you know it's late? (`ingested_at` vs `event_timestamp`)
- [ ] Resolution: Adjustment line item in Feb invoice? Recompute Jan window?
- [ ] Trade-off: Billing lag vs invoice immutability

### Reconciliation Process

**Question:** How do you verify window totals match raw events?

- [ ] Query to check: `SUM(units) from events WHERE ... = window.total_units`
- [ ] Frequency: On-demand? Nightly job?
- [ ] Drift correction: Manual adjustment vs automatic recomputation?

**Required:**

- Specific SQL queries for reconciliation
- Alerting threshold (>1% drift triggers investigation?)
- Who can trigger recomputation (ops only? automated?)

---

## 4. Failure Modes at Production Scale

**Must identify 3 specific bottlenecks with numbers:**

### Bottleneck #1: [Component Name]

- **When it breaks:** At X events/sec or Y customers or Z GB data
- **Symptom:** Observable behavior (timeouts, queue depth, error rate)
- **Root cause:** Why does it break? (Query scans N rows, job takes >interval)
- **Fix:** Specific implementation (add index X, partition by Y, shard on Z)
- **Cost:** Dev time + infrastructure cost
- **Result:** Scales to [new limit]

**Example standard:**

```
✓ GOOD: "Aggregator breaks at Day 6 (100M events accumulated). Query on
UsageEvent table takes >5min (exceeds job interval), JobLock prevents concurrent
runs, backlog builds. Fix: Add partial index on (customer_id, event_timestamp)
WHERE finalized=false + batch finalization after aggregation. Cost: 4 hours dev.
Scales to 500M events/month indefinitely."

✗ BAD: "Aggregator might be slow at scale. Add indexes to fix it."
```

### Check for:

- Timeline (Day 6, not "eventually")
- Specific numbers (100M rows, not "large table")
- Observable failure mode (what happens to users?)
- Implementation detail (not "make it faster" but "add partial index on...")

---

## 5. Threat Model with Concrete Abuse Scenarios

**Required for each threat actor:**

### Hostile Customer

**Goal:** Access other customers' data, inflate credits, avoid payment

**Attack 1: Cross-tenant access**

- Scenario: Customer A tries `GET /v1/invoices/{customer_b_invoice_id}`
- Defense: `get_object_or_404(Invoice, id=X, customer=self.customer)`
- Result: 404 Not Found (not 403, prevents info leakage)

**Attack 2: Replay old events**

- Scenario: Submit same request_id 1000 times to inflate usage
- Defense: UNIQUE(request_id), `bulk_create(ignore_conflicts=True)`
- Result: Only first event counted

**Attack 3: Guess API keys**

- Scenario: Brute force `sk_` prefix + random hex
- Defense: SHA256 hash (2^256 keyspace), rate limiting (if implemented)
- Result: Infeasible (would take [X] years at [Y] requests/sec)

### Hostile Internal User (Ops)

**Goal:** Issue fraudulent credits, tamper with invoices, hide activity

**Attack 1: Issue credit without audit trail**

- Scenario: Direct database INSERT into credits table
- Defense: Audit log created in same transaction, programmatically immutable
- Result: All credits logged with actor, cannot be hidden

**Attack 2: Delete audit logs**

- Scenario: `AuditLog.objects.filter(actor='ops-bob').delete()`
- Defense: `delete()` raises `PermissionError`, database-level revoke DELETE
- Result: Cannot delete through ORM or SQL (if permissions set)

**Attack 3: Modify invoice after generation**

- Scenario: Change total_cents on issued invoice
- Defense: Overrides create new line items (adjustments), AuditLog tracks before/after
- Result: Original line items preserved, changes visible in audit trail

### Compromised Webhook Source

**Goal:** Mark invoices as paid without payment, cause financial loss

**Attack 1: Replay legitimate webhook**

- Scenario: Capture valid webhook, replay 100 times
- Defense: UNIQUE(external_id), `get_or_create()` returns existing
- Result: Invoice marked paid once, replays ignored

**Attack 2: Forge webhook signature**

- Scenario: POST /webhooks/payments with guessed signature
- Defense: HMAC-SHA256 with secret, `hmac.compare_digest()` constant-time
- Result: Invalid signature rejected (401), no side effects

**Attack 3: Modify webhook payload**

- Scenario: Change invoice_id in payload after signature generated
- Defense: Signature covers entire body, modified body fails verification
- Result: Request rejected before processing

**Check for:**

- Specific attack steps (not just "try to hack")
- Code reference that implements defense
- Failure mode (what happens when attack attempted)
- Residual risk (what if database compromised? rate limiting missing?)

---

## 6. Non-Obvious Trade-offs

**Required: At least 2 decisions with alternatives and reasoning**

### Trade-off Template

**Decision:** [What you chose]
**Alternative rejected:** [Specific other approach]
**Why chosen:** [Technical reason with numbers/constraints]
**Cost:** [What you give up]
**When to revisit:** [At what scale does alternative become better?]

**Example:**

**Decision:** Cursor pagination (`base64(timestamp|id)`)
**Alternative rejected:** Offset pagination (LIMIT N OFFSET M)
**Why chosen:**

- Offset: 100 new events inserted between page 1 and page 2 → skip 100 events
- Cursor: Stable results even under concurrent writes
- Billing reconciliation needs correctness > convenience
  **Cost:**
- Can't jump to arbitrary page
- No total count (requires full table scan)
- More complex implementation
  **When to revisit:**
- Never for billing data (correctness requirement)
- Consider offset for internal reports (convenience > correctness)

**Non-obvious candidates:**

- Hourly windows vs real-time Redis counters
- Adjustment line items vs recompute past invoices
- UUIDs vs integer IDs
- Programmatic immutability vs database triggers
- APScheduler vs Celery for background jobs
- Table partitioning by month vs customer

**Check for:**

- Both alternatives named explicitly
- Numbers/constraints in reasoning (not just "feels better")
- Honest cost assessment (what you lose)
- Trigger point for revisiting (at X scale, alternative is better)

---

## 7. What You Didn't Build

**Required: Prioritized list with rationale**

### Not Built (Intentional Omissions)

**For each:**

- Feature name
- Why not built now (complexity, premature, not needed at current scale)
- When to build (trigger: X events/sec, Y customers, specific problem observed)

**Examples:**

- Rate limiting per API key (not needed at 5k customers, build at abuse observed)
- Read replicas (single DB handles current load, add at >10k events/sec sustained)
- Event timestamp validation (trust client for MVP, reject >1hr drift in production)
- Streaming aggregation (batch wins at 200/sec, need Flink at >10k/sec sustained)

### Would Build Next (Priority Order)

1. **[Feature]** - Why: [business value], Effort: [X days], Unblocks: [scale/feature]
2. **[Feature]** - Why: [business value], Effort: [X days], Unblocks: [scale/feature]
3. **[Feature]** - Why: [business value], Effort: [X days], Unblocks: [scale/feature]

**Check for:**

- Clear distinction between "didn't build" vs "would build next"
- Rationale (not just feature list)
- Effort estimates (relative sizing)
- Priority ordering (what's most valuable)

---

## Review Process

**For DESIGN.md, verify:**

1. **Specificity:** Every claim has numbers (100M rows, Day 6, 5min, 200/sec)
2. **Evidence:** Code references with file:line for key mechanisms
3. **Honesty:** Trade-offs acknowledge costs, not just benefits
4. **Completeness:** All 7 sections covered with required depth
5. **Actionability:** "Add index X" not "make it faster"
6. **Timeline:** "Day 6" not "at scale"
7. **Failure modes:** What breaks, when, why, how to fix

**Red flags:**

- Vague scaling claims ("millions of users")
- Missing numbers ("high throughput")
- No trade-offs discussed (every decision is perfect)
- No failure modes identified (system never breaks)
- Security = "we use HTTPS" (no threat scenarios)
- Indexes exist "for performance" (no query pattern)

**Word count target:** 1,800-2,500 words for design reasoning section

- Too short (<1,500): Likely missing depth or examples
- Too long (>3,000): Likely verbose, needs tightening

**Format check:**

- ASCII diagrams for architecture/flow
- Code snippets for key mechanisms (idempotency, locking)
- Tables for comparisons (cursor vs offset, alternatives)
- SQL for schema and indexes

---

## Output Format

After review, provide:

### ✅ Strengths

List 3-5 aspects that are well-covered with specific examples

### ⚠️ Gaps

List specific sections missing required detail:

- "Section 4: Only 2 failure modes listed, need 3"
- "Section 5: Hostile customer scenario missing defense code reference"

### 🔧 Suggested Additions

Concrete snippets or sections to add:

````markdown
Add to Section 2 (Idempotency):

**Concurrent credit issuance test:**

```python
# Test: 5 threads issue credit simultaneously
def test_concurrent_credit():
    with ThreadPoolExecutor(5) as executor:
        futures = [executor.submit(issue_credit, customer_id, 1000)
                   for _ in range(5)]
    assert Credit.objects.filter(customer=customer).count() == 1
```
````

```

### 📊 Metrics
- Word count: X (target 1,800-2,500)
- Code examples: X (need 5+ for concurrency/idempotency)
- Numbers/specifics: X instances (need 10+ for scale analysis)
- Trade-offs: X discussed (need 2+)

---

**Review Philosophy:**

Design documents demonstrate depth of thinking, not breadth of features. Each section should teach something non-obvious. Generic statements like "we use indexes for performance" or "system is scalable" provide no signal.

Strong design docs answer:
- **Why this approach?** (not just what)
- **What breaks first?** (with numbers)
- **What did you not build?** (honest omissions)
- **What would you do differently at 10×?** (specific changes)

Weak design docs list technologies and claim things work well.
```
