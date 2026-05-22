import uuid
from django.db import models


class UsageEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_id = models.CharField(max_length=255, unique=True)  # Idempotency key
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="usage_events"
    )
    api_key = models.ForeignKey(
        "customers.ApiKey", on_delete=models.PROTECT, related_name="usage_events"
    )
    endpoint = models.CharField(max_length=255)
    units = models.PositiveIntegerField()
    event_timestamp = models.DateTimeField()
    ingested_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"UsageEvent {self.request_id} - {self.units} units"

    class Meta:
        db_table = "usage_events"
        indexes = [
            models.Index(fields=["customer", "event_timestamp"]),
        ]


class UsageWindow(models.Model):
    id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="usage_windows"
    )
    window_start = models.DateTimeField()  # Hourly boundary
    window_end = models.DateTimeField()
    total_units = models.PositiveIntegerField()
    finalized = models.BooleanField(default=False)

    def __str__(self):
        return f"UsageWindow for {self.customer.name}: {self.window_start} - {self.total_units} units"

    class Meta:
        db_table = "usage_windows"
        unique_together = [("customer", "window_start")]
        indexes = [
            models.Index(fields=["customer", "window_start"]),
        ]
