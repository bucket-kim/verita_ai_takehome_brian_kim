"""
Test 3: Tenant isolation - Customer A cannot access Customer B's invoice
Should return 404, not 403 (to avoid revealing invoice existence)
"""
import pytest


@pytest.mark.django_db
def test_tenant_isolation(api_client, api_key_a, invoice_for_customer_b):
    """Test that Customer A cannot access Customer B's invoice."""
    # Try to access customer B's invoice with customer A's API key
    response = api_client.get(
        f'/v1/invoices/{invoice_for_customer_b.id}',
        HTTP_X_API_KEY=api_key_a.raw_key
    )

    # Should return 404 (not found), not 403 (forbidden)
    # This prevents revealing that the invoice exists
    assert response.status_code == 404, (
        f"Expected 404 for cross-tenant access, got {response.status_code}"
    )
