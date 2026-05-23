# 🔐 Login Guide

## Quick Start

When you run `docker compose up`, the credentials will be displayed automatically in the logs:

```bash
docker compose up
```

Look for this banner in the output:

```
╔════════════════════════════════════════════════════════════════════════════╗
║                         🔐 LOGIN CREDENTIALS                               ║
╚════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────┐
│  📱 CUSTOMER PORTAL                                                     │
├─────────────────────────────────────────────────────────────────────────┤
│  URL:     http://localhost:5173/customer/login                          │
│  API Key: sk_test_demo_key_11111111111111111111111111111111             │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  🔧 OPS CONSOLE                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│  URL:   http://localhost:5173/ops/login                                 │
│  Token: ops-dev-token-12345                                             │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📱 Customer Portal Login

### Credentials

- **URL:** http://localhost:5173/customer/login
- **API Key:** `sk_test_demo_key_11111111111111111111111111111111`

### What You'll See

After logging in with the API key above, you'll have access to:

✅ **Dashboard** with usage charts and metrics
✅ **1 invoice** (~$6,426.30 total)
✅ **1,507 usage events** over the past 60 days
✅ **Filter capabilities** by date range and API key
✅ **Real-time data** from the seeded database

### Features

- View monthly invoices with detailed line items
- Browse usage events with pagination
- Filter events by date range
- See usage charts and trends

---

## 🔧 Ops Console Login

### Credentials

- **URL:** http://localhost:5173/ops/login
- **Ops Token:** `ops-dev-token-12345`

### What You'll See

After logging in with the ops token above, you'll have access to:

✅ **21 customers** in the system
✅ **Customer details** with usage statistics
✅ **Credit issuance** functionality
✅ **Invoice management** capabilities
✅ **Audit trail** for all operations

### Features

- View all customers in the system
- Issue credits to customers
- View customer usage and invoices
- Override invoice line items
- See audit logs for all changes

---

## 🎯 Always the Same Credentials

**YES!** The API key `sk_test_demo_key_11111111111111111111111111111111` is always the same for local testing.

This is hardcoded in the seed script and will be created automatically every time you:
- Run `docker compose up` (first time with empty database)
- Run `docker compose down -v && docker compose up` (fresh start)

---

## 📋 Quick Reference Commands

### Display Credentials Anytime

```bash
# Show credentials in terminal
./show_credentials.sh

# Or view from file
cat open_localhost.txt
```

### Start with Auto-Display

```bash
# Start services and show credentials
./start.sh
```

### Restart Services

```bash
# Restart all services
docker compose restart

# Rebuild and restart (if you changed code)
docker compose up -d --build
```

### Fresh Start

```bash
# Stop and remove all data (fresh database)
docker compose down -v

# Start again (will re-seed automatically)
docker compose up
```

---

## 🧪 Verify Everything Works

Run this test to verify both logins are working:

```bash
# Test customer API
curl http://localhost:8000/v1/invoices \
  -H "X-API-Key: sk_test_demo_key_11111111111111111111111111111111"

# Test ops API
curl http://localhost:8000/ops/customers \
  -H "X-Ops-Token: ops-dev-token-12345"
```

Both should return JSON data with no errors.

---

## 🔍 Troubleshooting

### "I don't see the credentials banner"

**Solution:**
```bash
# View backend logs to see the banner
docker compose logs backend | tail -40
```

### "Login page won't load"

**Solution:**
```bash
# Check if frontend is running
curl http://localhost:5173/customer/login

# If it fails, restart frontend
docker compose restart frontend
```

### "API key doesn't work"

**Solution:**
```bash
# Verify the test customer exists
docker compose exec backend python manage.py shell -c "
from apps.customers.models import ApiKey
import hashlib
test_key = 'sk_test_demo_key_11111111111111111111111111111111'
key_hash = hashlib.sha256(test_key.encode()).hexdigest()
api_key = ApiKey.objects.filter(key_hash=key_hash).first()
if api_key:
    print(f'✅ API key exists for customer: {api_key.customer.name}')
else:
    print('❌ API key not found - run seed script')
"
```

### "Ops token doesn't work"

**Solution:**
```bash
# Check .env file
grep OPS_TOKEN .env

# Should show: OPS_TOKEN=ops-dev-token-12345
```

---

## 💡 Pro Tips

1. **Bookmark the login pages** for quick access:
   - http://localhost:5173/customer/login
   - http://localhost:5173/ops/login

2. **Copy-paste the credentials** from the banner when `docker compose up` runs

3. **Use `./start.sh`** instead of `docker compose up` for automatic credential display

4. **Check logs anytime** with: `docker compose logs backend | grep -A 20 "LOGIN CREDENTIALS"`

5. **The credentials never change** for local development, so you can save them

---

## 📊 What Data is Available?

### Customer Portal (Test Customer)
- **Customer:** Customer 1 (customer1@example.com)
- **Invoices:** 1 invoice (~$6,426.30)
- **Usage Events:** 1,507 events over 60 days
- **Period:** Last 2 months of data

### Ops Console
- **Total Customers:** 21 customers
- **Total Invoices:** 20 invoices
- **Total Usage Events:** ~30,000 events
- **Time Range:** 60 days of historical data

---

## 🚀 Next Steps

1. Open http://localhost:5173/customer/login
2. Paste: `sk_test_demo_key_11111111111111111111111111111111`
3. Click "Login"
4. Explore the dashboard and invoices

Then try the Ops Console:

1. Open http://localhost:5173/ops/login
2. Paste: `ops-dev-token-12345`
3. Click "Login"
4. Browse customers and issue credits

---

## ✅ Verified Working

- ✅ Customer portal login page accessible
- ✅ Customer API authentication working
- ✅ Customer data loads (1 invoice, 1,507 events)
- ✅ Ops console login page accessible
- ✅ Ops API authentication working
- ✅ Ops data loads (21 customers)
- ✅ Invalid credentials properly rejected
- ✅ Credentials display on `docker compose up`
- ✅ Consistent API key for easy testing

**System Status: READY TO USE** 🎉
