Build the Ops Console at /ops/\* using React + Vite + TypeScript + Tailwind.

Ops users authenticate with a static ops token stored in localStorage (simple login page).

Pages:

1. /ops/login — ops token input

2. /ops/customers — paginated customer list
   - Table: Name | Email | This Month Usage | Outstanding Balance | Anomaly Flag
   - Anomaly flag: show ⚠️ badge if customer's usage this month is >10× their 30-day average (compute client-side from usage data)
   - Cursor pagination with "Load more"
   - Click row → /ops/customers/:id

3. /ops/customers/:id — Customer detail
   - Customer info card (name, email, API key prefixes — never full keys)
   - Usage chart (same as customer dashboard, but ops can see any customer)
   - Invoice list table with status badges
   - "Issue Credit" button → opens modal

4. Credit issuance modal (on /ops/customers/:id):
   - Fields: Amount (dollar input, converts to cents), Reason (required text)
   - Confirmation step: "You are about to issue a $X.XX credit to [Customer Name]. This cannot be undone."
   - Submit button disabled until confirmation checkbox is checked
   - On submit: POST /ops/customers/{id}/credits with idempotency token (uuid generated client-side, sent as X-Idempotency-Key header)
   - Success → close modal, refetch customer data
   - Error → show error message in modal, keep modal open

5. /ops/invoices/:id/edit — Line item override
   - Show current line items
   - Each line item has an "Override" button
   - Override form: new total (dollar input), reason (required)
   - Confirmation: "Override line item [desc] from $X to $Y. Reason: [reason]. This will be logged."
   - On submit: PATCH /ops/invoices/{id}/line-items/{lid}
   - After save: show audit trail for this line item (fetched from audit log)

Safety requirements:

- All money-moving actions (credit, override) require a two-step confirmation
- Idempotency token generated fresh per action attempt (uuid v4)
- Show last 5 audit log entries on customer detail page
