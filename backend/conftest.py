import pytest
import hashlib
from django.utils import timezone
from rest_framework.test import APIClient
from apps.customers.models import Customer, ApiKey
from apps.billing.models import Invoice, InvoiceLineItem
from apps.ops.models import AuditLog


@pytest.fixture
def api_client():
    """Provides an API client for making requests."""
    return APIClient()


@pytest.fixture
def customer_a(db):
    """Create test customer A."""
    return Customer.objects.create(
        name="Customer A",
        email="customer_a@example.com"
    )


@pytest.fixture
def customer_b(db):
    """Create test customer B."""
    return Customer.objects.create(
        name="Customer B",
        email="customer_b@example.com"
    )


@pytest.fixture
def api_key_a(customer_a):
    """Create API key for customer A."""
    key = "sk_test_customer_a_key"
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    api_key = ApiKey.objects.create(
        customer=customer_a,
        key_hash=key_hash,
        key_prefix=key[:8]
    )
    api_key.raw_key = key  # Attach raw key for test usage
    return api_key


@pytest.fixture
def api_key_b(customer_b):
    """Create API key for customer B."""
    key = "sk_test_customer_b_key"
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    api_key = ApiKey.objects.create(
        customer=customer_b,
        key_hash=key_hash,
        key_prefix=key[:8]
    )
    api_key.raw_key = key  # Attach raw key for test usage
    return api_key


@pytest.fixture
def invoice_for_customer_b(customer_b):
    """Create an invoice for customer B."""
    now = timezone.now()
    invoice = Invoice.objects.create(
        customer=customer_b,
        period_start=now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
        period_end=now,
        status='issued',
        total_cents=10000
    )
    return invoice


@pytest.fixture
def ops_token():
    """Return the ops token from environment."""
    from django.conf import settings
    return settings.OPS_TOKEN
