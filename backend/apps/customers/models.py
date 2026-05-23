import uuid
from django.db import models


class Customer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_authenticated(self):
        """
        Always return True. This is required for DRF's IsAuthenticated permission.
        """
        return True

    def __str__(self):
        return f"{self.name} ({self.email})"

    class Meta:
        db_table = "customers"


class ApiKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="api_keys"
    )
    key_hash = models.CharField(max_length=64)  # SHA256 hash
    key_prefix = models.CharField(max_length=8)  # First 8 chars for display
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"ApiKey {self.key_prefix}*** for {self.customer.name}"

    class Meta:
        db_table = "api_keys"
