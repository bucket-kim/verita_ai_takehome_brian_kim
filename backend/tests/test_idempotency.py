"""
Test 1: Idempotency - POST /v1/events with same request_id twice
Should only create 1 row in UsageEvent table
"""
import pytest
from django.utils import timezone
from apps.usage.models import UsageEvent


@pytest.mark.django_db
def test_event_idempotency(api_client, api_key_a):
    """Test that posting the same event twice only creates one UsageEvent."""
    now = timezone.now()

    event_data = {
        'events': [{
            'request_id': 'test_request_123',
            'api_key_id': str(api_key_a.id),
            'endpoint': '/api/process',
            'units': 100,
            'timestamp': now.isoformat()
        }]
    }

    # First POST - should succeed
    response1 = api_client.post(
        '/v1/events',
        data=event_data,
        format='json',
        HTTP_X_API_KEY=api_key_a.raw_key
    )
    assert response1.status_code == 207

    # Second POST with same request_id - should succeed but not create duplicate
    response2 = api_client.post(
        '/v1/events',
        data=event_data,
        format='json',
        HTTP_X_API_KEY=api_key_a.raw_key
    )
    assert response2.status_code == 207

    # Verify only 1 row exists
    event_count = UsageEvent.objects.filter(request_id='test_request_123').count()
    assert event_count == 1, f"Expected 1 UsageEvent, found {event_count}"
