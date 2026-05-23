"""
Test 7: Tiered pricing correctness - generate invoice for 150,000 units
Line items should sum to correct cents:
- 10,000 units at 0 millicents = $0.00
- 90,000 units at 100 millicents = $900.00
- 50,000 units at 50 millicents = $250.00
- Total: $1,150.00 = 115,000 cents
"""
import pytest
from datetime import timedelta
from django.db.models import Sum
from django.utils import timezone
from apps.usage.models import UsageEvent, UsageWindow
from apps.billing.models import Invoice, InvoiceLineItem
from apps.billing.jobs import aggregate_usage_windows, generate_invoices


@pytest.mark.django_db
def test_tiered_pricing_correctness(customer_a, api_key_a):
    """Test that tiered pricing is calculated correctly for 150,000 units."""
    # Set up time for previous month
    now = timezone.now()
    first_of_current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Calculate previous month
    if first_of_current_month.month == 1:
        period_start = first_of_current_month.replace(year=first_of_current_month.year - 1, month=12)
    else:
        period_start = first_of_current_month.replace(month=first_of_current_month.month - 1)

    # Create usage events totaling exactly 150,000 units in previous month
    # Split across multiple hours to be realistic
    events_per_hour = 10
    units_per_event = 150000 // events_per_hour  # 15,000 units per event

    for i in range(events_per_hour):
        event_time = period_start + timedelta(hours=i * 24)  # One per day
        UsageEvent.objects.create(
            request_id=f'pricing_test_{i}',
            customer=customer_a,
            api_key=api_key_a,
            endpoint='/api/process',
            units=units_per_event,
            event_timestamp=event_time
        )

    # Aggregate usage windows
    aggregate_usage_windows()

    # Verify total units in windows
    total_units = UsageWindow.objects.filter(
        customer=customer_a,
        window_start__gte=period_start,
        window_start__lt=first_of_current_month
    ).aggregate(total=Sum('total_units'))['total'] or 0

    assert total_units == 150000, f"Expected 150,000 units, got {total_units}"

    # Generate invoices
    generate_invoices()

    # Get the invoice
    invoice = Invoice.objects.get(
        customer=customer_a,
        period_start=period_start
    )

    # Verify line items
    line_items = InvoiceLineItem.objects.filter(invoice=invoice).order_by('id')

    # Expected (10 millicents = 1 cent):
    # Tier 1: 10,000 units at 0 millicents = 0 millicents = 0 cents = $0.00
    # Tier 2: 90,000 units at 100 millicents = 9,000,000 millicents / 10 = 900,000 cents = $9,000.00
    # Tier 3: 50,000 units at 50 millicents = 2,500,000 millicents / 10 = 250,000 cents = $2,500.00
    # Total: 11,500,000 millicents / 10 = 1,150,000 cents = $11,500.00

    expected_line_items = [
        {'units': 10000, 'unit_price_millicents': 0, 'total_cents': 0},
        {'units': 90000, 'unit_price_millicents': 100, 'total_cents': 900000},
        {'units': 50000, 'unit_price_millicents': 50, 'total_cents': 250000}
    ]

    assert line_items.count() == 3, f"Expected 3 line items, got {line_items.count()}"

    for i, line_item in enumerate(line_items):
        expected = expected_line_items[i]
        assert line_item.units == expected['units'], (
            f"Line item {i}: expected {expected['units']} units, got {line_item.units}"
        )
        assert line_item.unit_price_millicents == expected['unit_price_millicents'], (
            f"Line item {i}: expected {expected['unit_price_millicents']} millicents, "
            f"got {line_item.unit_price_millicents}"
        )
        assert line_item.total_cents == expected['total_cents'], (
            f"Line item {i}: expected {expected['total_cents']} cents, got {line_item.total_cents}"
        )

    # Verify invoice total
    expected_total_cents = 1150000  # $11,500.00
    assert invoice.total_cents == expected_total_cents, (
        f"Expected {expected_total_cents} cents, got {invoice.total_cents}"
    )
