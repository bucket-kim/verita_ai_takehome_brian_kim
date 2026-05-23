"""
Test 6: Double credit prevention - concurrent POST /ops/customers/{id}/credits
Total credits applied should equal expected, not doubled
"""
import pytest
import threading
import uuid
from rest_framework.test import APIClient
from apps.billing.models import Credit


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrent
def test_double_credit_prevention(customer_a, ops_token):
    """Test that concurrent credit POSTs with same idempotency key only apply once."""
    idempotency_key = str(uuid.uuid4())
    credit_amount_cents = 5000  # $50.00
    reason = "Test credit for double-prevention"

    results = []

    def post_credit():
        """POST credit from a thread."""
        client = APIClient()
        try:
            response = client.post(
                f'/ops/customers/{customer_a.id}/credits',
                data={
                    'amount_cents': credit_amount_cents,
                    'reason': reason
                },
                format='json',
                HTTP_X_OPS_TOKEN=ops_token,
                HTTP_X_IDEMPOTENCY_KEY=idempotency_key
            )
            results.append(response.status_code)
        except Exception as e:
            results.append(str(e))

    # Create and start 5 threads with same idempotency key
    threads = []
    for _ in range(5):
        thread = threading.Thread(target=post_credit)
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Verify only 1 credit was created
    credit_count = Credit.objects.filter(
        customer=customer_a,
        idempotency_key=idempotency_key
    ).count()
    assert credit_count == 1, f"Expected 1 Credit, found {credit_count}"

    # Verify the credit amount is correct (not doubled)
    credit = Credit.objects.get(
        customer=customer_a,
        idempotency_key=idempotency_key
    )
    assert credit.amount_cents == credit_amount_cents, (
        f"Expected {credit_amount_cents} cents, got {credit.amount_cents}"
    )

    # Verify at least some requests succeeded
    success_count = sum(1 for r in results if r in [200, 201])
    assert success_count >= 1, f"Expected at least 1 successful POST, got {success_count}"
