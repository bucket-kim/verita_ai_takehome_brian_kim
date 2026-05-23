Build the Customer Dashboard SPA at /customer/\* using React + Vite + TypeScript + Tailwind + Recharts.

The app reads a customer API key from localStorage (set once on a simple /customer/login page with an API key input field).

Pages:

1. /customer/login
   - Input for API key, stores in localStorage, redirects to /customer/dashboard

2. /customer/dashboard
   - Header showing "Current billing period: [month]"
   - Usage chart: AreaChart (Recharts) showing daily total units for the current month
     - X-axis: date, Y-axis: units consumed
     - Fetch from GET /v1/usage with current month date range, aggregate by day client-side
   - Summary card: total units this period, estimated charge (compute from units × price tier client-side)
   - Loading skeleton while data fetches, error banner if fetch fails

3. /customer/invoices
   - Table: Period | Total | Status (badge: draft/issued/paid) | Actions
   - Cursor-based pagination with "Load more" button
   - Clicking a row navigates to /customer/invoices/:id

4. /customer/invoices/:id
   - Invoice header: period, status, total amount in dollars (format as $X.XX)
   - Line items table: Description | Units | Unit Price | Total
   - Back button

Design requirements:

- Money must always display as dollars with 2 decimal places, computed from integer cents
- Never display raw cents to the user
- All API calls use X-API-Key header from localStorage
- Axios instance in src/api/client.ts with base URL from import.meta.env.VITE_API_URL
- Extract useInvoices(), useUsage() custom hooks
- 401 response → redirect to /customer/login
