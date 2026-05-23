# Metered API Billing System

[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![Django](https://img.shields.io/badge/Django-4.2-green)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-18-blue)](https://reactjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)](https://www.postgresql.org/)

A production-grade metered billing system that tracks API usage, calculates tiered pricing, and generates invoices automatically. Built with Django REST Framework, React, and PostgreSQL.

> **⚡️ Demo ready in 60 seconds** | 🎯 Production patterns | 🔒 Security-first design

---

## What This Is

This system demonstrates how a real-world usage-based billing platform works:

- **Track API usage** - Customers submit events, system aggregates them hourly
- **Tiered pricing** - First 10k units free, then 0.1¢ per unit up to 100k, then 0.05¢ beyond
- **Monthly invoices** - Automatically generated on the 1st of each month
- **Ops console** - Issue credits, adjust invoices, view audit logs

**Key architectural decisions:**
- Idempotent APIs prevent duplicate charges
- Concurrency-safe operations using row locks
- Immutable audit trail for compliance
- Scales to millions of events with documented bottlenecks

---

## Quick Start

```bash
# Clone and enter directory
git clone https://github.com/bucket-kim/verita_ai_takehome_brian_kim.git
cd verita_ai_takehome_brian_kim

# Start everything (auto-seeds 20 customers + 30k events)
cp .env.example .env
./start.sh
```

**First startup takes ~30 seconds.** System automatically creates database, seeds data, and displays login credentials.

---

## Login & Test

After startup, you'll see credentials displayed. Or run: `./show_credentials.sh`

### Customer Portal
- **URL:** http://localhost:5173/customer/login
- **API Key:** `sk_test_demo_key_11111111111111111111111111111111`
- **What you'll see:** Usage dashboard, invoices (~$6,500), 1,500+ events

### Ops Console
- **URL:** http://localhost:5173/ops/login
- **Token:** `ops-dev-token-12345`
- **What you'll see:** Customer management, credit issuance, audit logs

---

## Key Features

### For Customers
- Real-time usage dashboard with charts
- Detailed invoices with tiered pricing breakdown
- Filterable usage events with pagination
- API access via secure API keys

### For Operations
- Manage all customers and their usage
- Issue credits with audit trail
- Override invoice line items with reason tracking
- View immutable audit logs for compliance

### Technical Highlights
- **Concurrency-safe:** Row locks prevent race conditions
- **Idempotent:** Duplicate requests don't create duplicate charges
- **Tenant isolation:** Customers can't see each other's data
- **Production patterns:** HMAC webhooks, SHA256 hashed keys, cursor pagination

---

## Architecture

```
React Frontend (TypeScript + TailwindCSS)
    ↓
Django REST API (Customer /v1/* + Ops /ops/* endpoints)
    ↓
PostgreSQL (Usage events, invoices, audit logs)
    ↓
Background Jobs (Hourly aggregation, monthly invoicing)
```

**Scale characteristics:**
- Current: 200 events/sec, 20 customers
- Bottleneck: Aggregator at 2000 events/sec (needs sharding)
- Solution path: Horizontal scaling, read replicas, partitioning

See [DESIGN.md](DESIGN.md) for detailed architecture and scaling analysis.

---

## Technology Stack

- **Backend:** Django 4.2, Django REST Framework, PostgreSQL 15
- **Frontend:** React 18, TypeScript, Vite, TailwindCSS, Recharts
- **Infrastructure:** Docker Compose, APScheduler
- **Testing:** pytest, ESLint, TypeScript compiler

---

## Documentation

- **[DESIGN.md](DESIGN.md)** - Architecture decisions, scaling analysis, trade-offs
- **[CLAUDE.md](CLAUDE.md)** - Development guidelines and coding conventions
- **[LOGIN_GUIDE.md](LOGIN_GUIDE.md)** - Detailed login instructions and troubleshooting

---

## Development

```bash
# Run backend tests
docker-compose exec backend pytest tests/ -v

# Run frontend checks
cd frontend && npm run lint && npx tsc --noEmit

# Access database
psql postgresql://postgres:postgres@localhost:5432/metered_billing

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

**Need help?** See [CLAUDE.md](CLAUDE.md) for complete command reference and troubleshooting.

---

## Contact

**Project by:** Brian Kim

- 📧 Email: brian.kyounghoon.kim@gmail.com
- 💼 Website: https://bkim-web.vercel.app/

---

**Built with:** Django • React • PostgreSQL • Docker • TypeScript • TailwindCSS

⭐ **If you found this interesting, please star the repo!**
