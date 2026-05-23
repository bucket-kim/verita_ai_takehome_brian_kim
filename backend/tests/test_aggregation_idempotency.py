"""
Test 4: Aggregation idempotency - run aggregate_usage_windows() twice
UsageWindow totals should remain unchanged
"""
import pytest
from datetime import timedelta
from django.utils import timezone
from apps.usage.models import UsageEvent, UsageWindow
from apps.billing.jobs import aggregate_usage_windows


@pytest.mark.django_db
def test_aggregation_idempotency(customer_a, api_key_a):
    """Test that running aggregate_usage_windows twice produces same result."""
    now = timezone.now()
    hour_start = now.replace(minute=0, second=0, microsecond=0)

    # Create usage events for customer A in the same hour
    for i in range(5):
        UsageEvent.objects.create(
            request_id=f'agg_test_{i}',
            customer=customer_a,
            api_key=api_key_a,
            endpoint='/api/process',
            units=100 + i * 10,  # 100, 110, 120, 130, 140
            event_timestamp=hour_start + timedelta(minutes=i * 10)
        )

    # First aggregation
    aggregate_usage_windows()

    # Get the usage window
    window = UsageWindow.objects.get(
        customer=customer_a,
        window_start=hour_start
    )
    first_total = window.total_units

    # Verify the total is correct (100 + 110 + 120 + 130 + 140 = 600)
    assert first_total == 600, f"Expected 600 units, got {first_total}"

    # Run aggregation again
    aggregate_usage_windows()

    # Get the window again and verify total is unchanged
    window.refresh_from_db()
    second_total = window.total_units

    assert second_total == first_total, (
        f"Aggregation not idempotent: first={first_total}, second={second_total}"
    )

    # Verify still only one window
    window_count = UsageWindow.objects.filter(
        customer=customer_a,
        window_start=hour_start
    ).count()
    assert window_count == 1, f"Expected 1 window, found {window_count}"
