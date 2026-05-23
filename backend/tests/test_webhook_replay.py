"""
Test 5: Webhook replay protection - POST /webhooks/payments with same external_id twice
Invoice status should update only once, only 1 WebhookDelivery row created
"""
import pytest
import hmac
import hashlib
import json
from django.conf import settings
from apps.billing.models import Invoice
from apps.ops.models import WebhookDelivery


@pytest.mark.django_db
def test_webhook_replay_protection(api_client, customer_a):
    """Test that replaying a webhook doesn't double-process."""
    # Create an invoice for customer A
    from django.utils import timezone
    now = timezone.now()
    invoice = Invoice.objects.create(
        customer=customer_a,
        period_start=now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
        period_end=now,
        status='issued',
        total_cents=10000
    )

    # Prepare webhook payload
    payload = {
        'external_id': 'payment_webhook_123',
        'invoice_id': str(invoice.id),
        'amount': 100.00,
        'status': 'paid'
    }

    # Serialize payload to JSON bytes (DRF will do this same way)
    payload_json = json.dumps(payload)
    payload_bytes = payload_json.encode('utf-8')

    # Generate HMAC signature
    signature = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()

    # First webhook POST - should succeed
    # Use generic client to send raw JSON with exact signature
    response1 = api_client.generic(
        'POST',
        '/webhooks/payments',
        data=payload_json,
        content_type='application/json',
        HTTP_X_WEBHOOK_SIGNATURE=signature
    )
    assert response1.status_code == 200

    # Verify invoice status updated
    invoice.refresh_from_db()
    assert invoice.status == 'paid'
    assert invoice.paid_at is not None

    # Verify webhook delivery recorded
    delivery_count = WebhookDelivery.objects.filter(external_id='payment_webhook_123').count()
    assert delivery_count == 1

    # Second webhook POST with same external_id - should be idempotent
    response2 = api_client.generic(
        'POST',
        '/webhooks/payments',
        data=payload_json,
        content_type='application/json',
        HTTP_X_WEBHOOK_SIGNATURE=signature
    )
    assert response2.status_code == 200

    # Verify still only 1 webhook delivery
    delivery_count = WebhookDelivery.objects.filter(external_id='payment_webhook_123').count()
    assert delivery_count == 1, f"Expected 1 WebhookDelivery, found {delivery_count}"

    # Verify invoice still marked as paid
    invoice.refresh_from_db()
    assert invoice.status == 'paid'
