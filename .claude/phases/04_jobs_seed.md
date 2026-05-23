Add background jobs and a seed script to the Django backend.

Create apps/billing/jobs.py:

1. aggregate_usage_windows()
   - Use transaction.atomic() + select_for_update(skip_locked=True) on a
     JobLock model (add to ops/models.py: JobLock with name CharField unique, locked_at)
   - Query UsageEvent grouped by (customer_id, truncated hour) not yet in a UsageWindow
   - Use Django ORM: UsageEvent.objects.filter(...).values('customer_id', hour=TruncHour('event_timestamp')).annotate(total=Sum('units'))
   - UsageWindow.objects.update_or_create(customer=..., window_start=..., defaults={total_units=...})
   - Idempotent: running twice produces same result

2. generate_invoices()
   - For each customer, find finalized UsageWindows for previous calendar month
     not yet covered by an Invoice
   - Apply tiered pricing from PricePlan:
     first 10,000 units: 0 millicents
     next 90,000 units: 100 millicents each (= $0.001)
     beyond 100,000: 50 millicents each (= $0.0005)
   - All arithmetic in integer millicents, convert to cents only at Invoice.total_cents
   - Use get_or_create(customer=..., period_start=..., period_end=...) to stay idempotent

Create management/commands/seed.py (Django management command):

- python manage.py seed
- Creates 20 Customer records, each with 1-2 ApiKey records
- For each ApiKey: generate the plaintext key as "sk\_" + secrets.token_hex(24),
  store key_hash = hashlib.sha256(plaintext.encode()).hexdigest(),
  store key_prefix = plaintext[:8]
- Print one sample customer's plaintext API key to stdout (only time plaintext exists)
- Generate ~50,000 UsageEvents spread over 60 days with realistic patterns:
  higher units during 9am-6pm, random late events with timestamps 2-3 hours behind ingestion time
- After inserting events, call aggregate_usage_windows() then generate_invoices()

Schedule jobs using APScheduler in apps/billing/apps.py ready() method:

- aggregate_usage_windows: every 5 minutes
- generate_invoices: cron, day=1, hour=0 (1st of month, midnight)
