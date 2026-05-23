# Metered API Billing System

[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![Django](https://img.shields.io/badge/Django-4.2-green)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-18-blue)](https://reactjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)](https://www.postgresql.org/)

A production-ready metered API billing system with Django REST Framework backend, React frontend, and PostgreSQL database. Supports usage tracking, tiered pricing, invoice generation, and ops console for customer management.

> **⚡️ Demo Ready in 60 seconds** | 🎯 Production-grade architecture | 🔒 Security-first design

## 📑 Table of Contents

- [Quick Start](#quick-start) - Get running in 60 seconds
- [Test Credentials](#-test-credentials-ready-to-use) - Login information
- [Screenshots](#-screenshots) - See the system in action
- [Key Features](#key-features) - What this system does
- [API Examples](#api-examples) - How to use the API
- [Architecture](#architecture-overview) - System design
- [Development](#development) - Contributing guide
- [Testing](#testing) - Run tests
- [Troubleshooting](#troubleshooting) - Common issues
- [Project Structure](#project-structure) - Code organization

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Git

### One-Command Setup

**🚀 Get running in 60 seconds:**

```bash
# Clone the repository
git clone <repository-url>
cd verita_ai_takehome_brian_kim

# Set up environment (uses safe defaults for local dev)
cp .env.example .env

# Start everything (auto-seeds with realistic data)
./start.sh
# ✅ Starts backend, frontend, database
# ✅ Creates 20 customers with 30k usage events
# ✅ Displays login credentials automatically
```

**⏱️ First startup takes ~30 seconds** (downloading Docker images + seeding data)

**Alternative (without auto-display):**
```bash
docker compose up --build
```

**That's it!** The system automatically:
- ✅ Creates all database tables (migrations)
- ✅ Generates realistic seed data (20 customers, ~30k events, invoices)
- ✅ Starts all services
- ✅ Displays login credentials (when using start.sh)

Once you see the credentials banner, you're ready to login! 🎉

**What gets created automatically:**
- 20 customers with API keys
- ~30,000 usage events over 60 days
- Aggregated hourly usage windows
- Generated invoices with tiered pricing ($6,000-$7,000 per customer)

**Services running:**
- **Backend API** on http://localhost:8000
- **Frontend** on http://localhost:5173
- **PostgreSQL** on localhost:5432

## 🔑 Test Credentials (Ready to Use)

**📖 See [LOGIN_GUIDE.md](LOGIN_GUIDE.md) for detailed login instructions and troubleshooting**

After `docker compose up` completes, **credentials will be displayed in the logs**. Use these to test the system:

### Customer Portal Login
- **URL:** http://localhost:5173/customer/login
- **API Key:** `sk_test_demo_key_11111111111111111111111111111111`
- **Customer:** Customer 1 (customer1@example.com)

**What you'll see:**
- Usage dashboard with charts showing ~30k events
- Monthly invoice: ~$6,500-$7,000
- Filterable usage events by date and API key

### Ops Console Login
- **URL:** http://localhost:5173/ops/login
- **Ops Token:** `ops-dev-token-12345` (from `.env` file)

**What you'll see:**
- List of 20 customers with usage statistics
- Customer detail pages with invoices
- Credit issuance form with audit trail
- Invoice line item override capability

---

**Note:** These credentials are automatically created by the seed script and work out of the box for local testing.

### 💡 View Credentials Anytime

After the system is running, you can display login credentials at any time:

```bash
# Display credentials in terminal
./show_credentials.sh

# Or view the saved file
cat open_localhost.txt
```

The `start.sh` script automatically displays credentials when starting the system.

## 📸 Screenshots

### Customer Portal

**Dashboard with Usage Analytics**
![Customer Dashboard](docs/screenshots/customer-dashboard.png)
*Real-time usage tracking with interactive charts showing 30k+ events over 60 days*

**Invoice Details**
![Invoice Detail](docs/screenshots/invoice-detail.png)
*Detailed invoices with tiered pricing breakdown and line items*

**Usage Events**
![Usage Events](docs/screenshots/usage-events.png)
*Filterable usage events with cursor pagination*

### Ops Console

**Customer Management**
![Customer List](docs/screenshots/ops-customers.png)
*View all customers with usage statistics and anomaly detection*

**Customer Detail & Credit Issuance**
![Customer Detail](docs/screenshots/ops-customer-detail.png)
*Issue credits, view invoices, and manage individual customers*

**Audit Trail**
![Audit Logs](docs/screenshots/ops-audit.png)
*Immutable audit logs for compliance and debugging*

> **Note:** Screenshots show the actual working system. To see it yourself, follow the [Quick Start](#quick-start) guide above.

## Seed Script Details

The system automatically generates realistic data on first startup using `manage.py seed`:

**What Gets Generated:**

1. **20 Test Customers**
   - Realistic names (Customer 1, Customer 2, etc.)
   - Email addresses (customer1@example.com, etc.)
   - 1-3 API keys per customer

2. **~30,000 Usage Events** (distributed over 60 days)
   - Random timestamps across business hours
   - Multiple API endpoints: `/chat`, `/search`, `/embeddings`
   - Varying usage: 1-1000 units per request
   - Realistic distribution: some customers use more than others

3. **Hourly Aggregation Windows**
   - Events aggregated into hourly buckets
   - Pre-computed totals for fast invoice generation
   - ~18,000 usage windows created

4. **Monthly Invoices** (one per customer)
   - Tiered pricing applied: 0¢ (first 10k), 0.1¢ (next 100k), 0.05¢ (over 110k)
   - Line items broken down by pricing tier
   - Total amounts: $6,000-$7,000 per customer
   - Status: "issued" (unpaid)

**Idempotency:** The seed script checks if data exists first. If customers are found, it skips seeding. This means running `docker compose up` multiple times won't duplicate data.

**Manual Re-seed:** To reset the database and regenerate data:
```bash
docker compose down -v  # Warning: deletes all data!
docker compose up
```

## Architecture Overview

```
┌─────────────────┐      ┌──────────────────┐      ┌──────────────┐
│  React Frontend │─────▶│  Django Backend  │─────▶│  PostgreSQL  │
│  (Vite + TS)    │ CORS │  (REST API)      │      │  Database    │
│  Port 5173      │◀─────│  Port 8000       │◀─────│  Port 5432   │
└─────────────────┘      └──────────────────┘      └──────────────┘
                                  │
                                  │ Background Jobs
                                  ▼
                         ┌─────────────────┐
                         │  APScheduler    │
                         │  - Aggregate    │
                         │  - Invoice Gen  │
                         └─────────────────┘
```

**Key Components:**
- **Customer API** (`/v1/*`) - Usage tracking, invoice retrieval (API key auth)
- **Ops API** (`/ops/*`) - Customer management, credit issuance (ops token auth)
- **Background Jobs** - Hourly aggregation every 5 minutes, invoice generation monthly
- **Frontend** - Customer portal and ops console with React Router

See [DESIGN.md](./DESIGN.md) for detailed architecture and design decisions.

## Testing

### Run All Tests
```bash
docker-compose build && docker-compose up -d
docker-compose exec backend pytest tests/ -v
cd frontend && npm run lint && npx tsc --noEmit
```

### Quick Health Check
```bash
docker-compose ps  # Verify all services running
curl -s http://localhost:8000/v1/invoices -H "X-API-Key: test" -o /dev/null -w "%{http_code}\n"
curl -s http://localhost:5173 -o /dev/null -w "%{http_code}\n"
```

### Test CORS Configuration
```bash
curl -s -I http://localhost:8000/v1/invoices \
  -H "Origin: http://localhost:5173" \
  | grep access-control
```

Expected: `access-control-allow-origin: http://localhost:5173`

## Development

### Backend Development
```bash
# Run tests
docker-compose exec backend pytest

# Create migrations
docker-compose exec backend python manage.py makemigrations

# Apply migrations
docker-compose exec backend python manage.py migrate

# Django shell
docker-compose exec backend python manage.py shell

# Access PostgreSQL
psql postgresql://postgres:postgres@localhost:5432/metered_billing
```

### Frontend Development
```bash
cd frontend

# Install dependencies
npm install

# Run linting
npm run lint

# Type check
npx tsc --noEmit

# Build for production
npm run build
```

**Note:** Frontend hot reload works for most changes. Restart frontend container after adding new routes:
```bash
docker-compose restart frontend
```

## Key Features

### Usage Tracking
- **Event ingestion:** POST bulk events with idempotency (request_id)
- **Aggregation:** Hourly windows updated every 5 minutes
- **Cursor pagination:** Stateless pagination with `timestamp|id` cursors

### Billing
- **Tiered pricing:** 0¢ (0-10k units), 0.1¢ (10k-100k), 0.05¢ (100k+)
- **Invoice generation:** Automatic monthly invoices on 1st at midnight
- **Late events:** Adjustment line items in next invoice (maintains immutability)

### Operations
- **Customer management:** View all customers, usage, and invoices
- **Credit issuance:** Add credits with audit trail
- **Manual adjustments:** Override line items with reason tracking

### Security
- **Authentication:** SHA256-hashed API keys, HMAC webhook signatures
- **Tenant isolation:** Customer-scoped queries prevent cross-tenant access
- **Audit logging:** Immutable logs for all ops actions

## API Examples

### Submit Usage Events (Customer)
```bash
curl -X POST http://localhost:8000/v1/events \
  -H "X-API-Key: sk_..." \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {
        "request_id": "unique-id-123",
        "api_key_id": "uuid",
        "endpoint": "/api/chat",
        "units": 150,
        "timestamp": "2026-05-23T12:00:00Z"
      }
    ]
  }'
```

### List Invoices (Customer)
```bash
curl http://localhost:8000/v1/invoices \
  -H "X-API-Key: sk_..."
```

### Issue Credit (Ops)
```bash
curl -X POST http://localhost:8000/ops/customers/{customer_id}/credits \
  -H "X-Ops-Token: your-ops-token-here" \
  -H "Content-Type: application/json" \
  -d '{
    "amount_cents": 1000,
    "reason": "Service outage credit"
  }'
```

## Troubleshooting

### Services Not Starting
```bash
docker-compose down
docker-compose up --build
docker-compose logs backend
docker-compose logs frontend
```

### Database Issues
```bash
# Reset database (WARNING: destroys all data)
docker-compose down -v
docker-compose up -d
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py seed
```

### CORS Errors
If browser console shows CORS errors:
1. Verify `backend/config/settings/dev.py` has `CORS_ALLOW_HEADERS` with custom headers
2. Restart backend: `docker-compose restart backend`
3. Check CORS headers: `curl -I http://localhost:8000/v1/invoices -H "Origin: http://localhost:5173"`

### Frontend Not Loading
1. Check Vite is running: `docker-compose logs frontend`
2. Verify `vite.config.ts` has `server: { host: '0.0.0.0', port: 5173 }`
3. Restart: `docker-compose restart frontend`

## Project Structure

```
.
├── backend/
│   ├── apps/
│   │   ├── billing/       # Invoice, InvoiceLineItem, Credit models
│   │   ├── customers/     # Customer, ApiKey models
│   │   ├── ops/          # Ops endpoints, AuditLog
│   │   └── usage/        # UsageEvent, UsageWindow models
│   ├── config/           # Django settings, URLs
│   └── tests/            # pytest test suite
├── frontend/
│   └── src/
│       ├── api/          # Axios clients (customer, ops)
│       ├── components/   # Shared UI components
│       ├── hooks/        # React hooks for data fetching
│       ├── pages/        # Route components
│       └── types/        # TypeScript interfaces
├── docker-compose.yml    # Service orchestration
├── DESIGN.md            # Architecture and design decisions
└── README.md            # This file
```

## Technology Stack

- **Backend:** Django 4.2, Django REST Framework, PostgreSQL
- **Frontend:** React 18, TypeScript, Vite, TailwindCSS, Recharts
- **Infrastructure:** Docker Compose, PostgreSQL 15
- **Background Jobs:** APScheduler
- **Testing:** pytest (backend), ESLint + TypeScript (frontend)

## Performance Characteristics

Current capacity (seed data scale):
- 20 customers, 30k events, 60 days
- Event ingestion: ~200 events/sec
- Aggregation: 5min windows, processes in <10sec
- Invoice generation: <5sec for 20 customers

See [DESIGN.md](./DESIGN.md) for scalability analysis and bottlenecks.

## 📄 Documentation

- **[DESIGN.md](DESIGN.md)** - Architecture decisions, scaling analysis, trade-offs
- **[CLAUDE.md](CLAUDE.md)** - Development guidelines and coding conventions
- **[LOGIN_GUIDE.md](LOGIN_GUIDE.md)** - Detailed login instructions and troubleshooting
- **[.claude/rules/](/.claude/rules/)** - Testing procedures, security verification, API requirements

## 📄 License

This project is licensed under the MIT License.

```
MIT License

Copyright (c) 2026 [Your Name]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 🤝 Contributing

This is a take-home project demonstration showcasing production-grade system design.

**Key Resources:**
- Review [DESIGN.md](DESIGN.md) for architecture and design decisions
- See [CLAUDE.md](CLAUDE.md) for development conventions and patterns
- Check [LOGIN_GUIDE.md](LOGIN_GUIDE.md) for testing the system

**To run tests:**
```bash
# Backend tests
docker-compose exec backend pytest tests/ -v

# Frontend tests
cd frontend && npm run lint && npx tsc --noEmit
```

## 📧 Contact

**Project by:** Brian Kim

For questions about this implementation:
- 📧 Email: [brian.kyounghoon.kim@gmail.com]
- 💼 Website: [https://bkim-web.vercel.app/]

---

**Built with:** Django • React • PostgreSQL • Docker • TypeScript • TailwindCSS

⭐ **If you found this interesting, please star the repo!**
