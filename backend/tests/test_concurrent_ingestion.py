"""
Test 2: Concurrent ingestion - POST same request_id from 10 concurrent threads
Should create exactly 1 row in UsageEvent table
"""
import pytest
import threading
from django.utils import timezone
from rest_framework.test import APIClient
from apps.usage.models import UsageEvent


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrent
def test_concurrent_event_ingestion(api_key_a):
    """Test that concurrent POSTs with same request_id only create one UsageEvent."""
    now = timezone.now()
    request_id = 'concurrent_test_123'

    event_data = {
        'events': [{
            'request_id': request_id,
            'api_key_id': str(api_key_a.id),
            'endpoint': '/api/process',
            'units': 100,
            'timestamp': now.isoformat()
        }]
    }

    results = []

    def post_event():
        """POST event from a thread."""
        client = APIClient()
        try:
            response = client.post(
                '/v1/events',
                data=event_data,
                format='json',
                HTTP_X_API_KEY=api_key_a.raw_key
            )
            results.append(response.status_code)
        except Exception as e:
            results.append(str(e))

    # Create and start 10 threads
    threads = []
    for _ in range(10):
        thread = threading.Thread(target=post_event)
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Verify only 1 row exists
    event_count = UsageEvent.objects.filter(request_id=request_id).count()
    assert event_count == 1, f"Expected 1 UsageEvent, found {event_count}. Results: {results}"

    # Verify that at least some requests succeeded
    success_count = sum(1 for r in results if r == 207)
    assert success_count >= 1, f"Expected at least 1 successful POST, got {success_count}"
