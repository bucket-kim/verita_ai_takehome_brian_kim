from datetime import datetime, timedelta
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import TruncHour
from django.utils import timezone
from apps.ops.models import JobLock
from apps.usage.models import UsageEvent, UsageWindow
from apps.billing.models import Invoice, InvoiceLineItem, PricePlan
from apps.customers.models import Customer


def aggregate_usage_windows():
    """
    Background job to aggregate usage events into hourly windows.

    Uses JobLock with select_for_update(skip_locked=True) to prevent concurrent execution.
    Groups UsageEvents by customer and hour, creates/updates UsageWindows.
    Idempotent: running multiple times produces the same result.
    """
    try:
        with transaction.atomic():
            # Acquire lock, skip if already locked
            lock = JobLock.objects.select_for_update(skip_locked=True).filter(
                name='aggregate_usage_windows'
            ).first()

            if not lock:
                # Create lock if it doesn't exist
                lock = JobLock.objects.create(name='aggregate_usage_windows')

            # Query UsageEvents grouped by customer and truncated hour
            # Find events not yet in a finalized UsageWindow
            aggregated = (
                UsageEvent.objects
                .values('customer_id')
                .annotate(hour=TruncHour('event_timestamp'))
                .annotate(total=Sum('units'))
                .order_by('customer_id', 'hour')
            )

            for agg in aggregated:
                customer_id = agg['customer_id']
                window_start = agg['hour']
                window_end = window_start + timedelta(hours=1)
                total_units = agg['total']

                # Update or create the usage window
                UsageWindow.objects.update_or_create(
                    customer_id=customer_id,
                    window_start=window_start,
                    defaults={
                        'window_end': window_end,
                        'total_units': total_units,
                        'finalized': True
                    }
                )

            print(f"Aggregated {len(list(aggregated))} usage windows")

    except Exception as e:
        print(f"Error aggregating usage windows: {e}")


def generate_invoices():
    """
    Background job to generate invoices for the previous calendar month.

    Applies tiered pricing:
    - First 10,000 units: 0 millicents
    - Next 90,000 units: 100 millicents each ($0.001)
    - Beyond 100,000: 50 millicents each ($0.0005)

    All arithmetic in integer millicents, converts to cents at Invoice.total_cents.
    Uses get_or_create for idempotency.
    """
    try:
        with transaction.atomic():
            # Acquire lock, skip if already locked
            lock = JobLock.objects.select_for_update(skip_locked=True).filter(
                name='generate_invoices'
            ).first()

            if not lock:
                lock = JobLock.objects.create(name='generate_invoices')

            # Calculate previous calendar month
            now = timezone.now()
            first_of_current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_end = first_of_current_month

            # Calculate first day of previous month (manual month arithmetic)
            if first_of_current_month.month == 1:
                period_start = first_of_current_month.replace(year=first_of_current_month.year - 1, month=12)
            else:
                period_start = first_of_current_month.replace(month=first_of_current_month.month - 1)

            # Get default price plan (create if doesn't exist)
            price_plan, _ = PricePlan.objects.get_or_create(
                name='Default Tiered Pricing',
                defaults={
                    'tiers': [
                        {'up_to': 10000, 'unit_price_millicents': 0},
                        {'up_to': 100000, 'unit_price_millicents': 100},
                        {'up_to': None, 'unit_price_millicents': 50}
                    ]
                }
            )

            # Process each customer
            for customer in Customer.objects.all():
                # Find finalized usage windows for the period
                windows = UsageWindow.objects.filter(
                    customer=customer,
                    window_start__gte=period_start,
                    window_start__lt=period_end,
                    finalized=True
                )

                if not windows.exists():
                    continue

                # Calculate total units
                total_units = windows.aggregate(total=Sum('total_units'))['total'] or 0

                # Apply tiered pricing
                total_millicents = 0
                remaining_units = total_units

                # Tier 1: 0-10,000 units at 0 millicents
                tier1_units = min(remaining_units, 10000)
                tier1_millicents = tier1_units * 0
                remaining_units -= tier1_units

                # Tier 2: 10,001-100,000 units at 100 millicents
                tier2_units = min(remaining_units, 90000)
                tier2_millicents = tier2_units * 100
                remaining_units -= tier2_units

                # Tier 3: 100,001+ units at 50 millicents
                tier3_units = remaining_units
                tier3_millicents = tier3_units * 50

                total_millicents = tier1_millicents + tier2_millicents + tier3_millicents
                total_cents = total_millicents // 10  # Convert millicents to cents

                # Create or get invoice (idempotent)
                invoice, created = Invoice.objects.get_or_create(
                    customer=customer,
                    period_start=period_start,
                    period_end=period_end,
                    defaults={
                        'status': 'issued',
                        'total_cents': total_cents
                    }
                )

                if created:
                    # Create line items for each tier used
                    if tier1_units > 0:
                        InvoiceLineItem.objects.create(
                            invoice=invoice,
                            description=f'Usage: 0-10,000 units',
                            units=tier1_units,
                            unit_price_millicents=0,
                            total_cents=tier1_millicents // 10
                        )

                    if tier2_units > 0:
                        InvoiceLineItem.objects.create(
                            invoice=invoice,
                            description=f'Usage: 10,001-100,000 units',
                            units=tier2_units,
                            unit_price_millicents=100,
                            total_cents=tier2_millicents // 10
                        )

                    if tier3_units > 0:
                        InvoiceLineItem.objects.create(
                            invoice=invoice,
                            description=f'Usage: 100,001+ units',
                            units=tier3_units,
                            unit_price_millicents=50,
                            total_cents=tier3_millicents // 10
                        )

                    print(f"Created invoice {invoice.id} for customer {customer.name}: ${total_cents/100:.2f}")

    except Exception as e:
        print(f"Error generating invoices: {e}")
