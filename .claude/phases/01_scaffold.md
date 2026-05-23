Create a monorepo for a metered API billing system with this structure:

/
├── backend/ # Django + Django REST Framework + PostgreSQL
│ ├── manage.py
│ ├── requirements.txt
│ ├── config/ # Django project settings (settings.py, urls.py, wsgi.py)
│ └── apps/
│ ├── customers/
│ ├── usage/
│ ├── billing/
│ └── ops/
├── frontend/ # React + Vite + TypeScript
├── docker-compose.yml
├── .env.example
└── DESIGN.md (placeholder)

Backend requirements:

- Django 4.2 + Django REST Framework
- psycopg2-binary for PostgreSQL
- django-environ for env config
- djangorestframework + markdown + django-filter
- APScheduler for background jobs
- No secrets in code — all via .env

Django settings:

- Split into base/dev/prod (config/settings/)
- Use django-environ to read DATABASE_URL, SECRET_KEY, WEBHOOK_SECRET from .env
- INSTALLED_APPS includes: rest_framework, django_filters, and all four apps
- REST_FRAMEWORK default authentication: custom ApiKeyAuthentication (to be implemented)
- Store money as IntegerField (cents) always — never DecimalField or FloatField

Frontend requirements:

- React 19 (latest: 19.2.6)
- Vite 8 as the build tool
- TypeScript (strict mode, no any)
- react-router v7 — import everything from "react-router", do NOT install react-router-dom
- Tailwind CSS v4 — use the @tailwindcss/vite plugin, NO tailwind.config.js file,
  configure via @theme blocks in main CSS file
- Recharts 3 for usage charts
- Axios for API calls

React 19 patterns to use:

- Use the new `use()` hook for promise unwrapping where appropriate
- Use `useOptimistic` for credit/override confirmation UI
- Use React 19 Actions for form submissions (replace manual useState loading patterns)
- Avoid useEffect for data fetching — use Suspense + resource patterns instead

Docker Compose should spin up:

1. postgres service (postgres:15)
2. backend service (python manage.py runserver 0.0.0.0:8000)
3. frontend service (vite dev, port 5173)

Create .env.example with placeholders for:
DATABASE_URL, SECRET_KEY, WEBHOOK_SECRET, OPS_TOKEN

Do not put any real secrets in any file.
