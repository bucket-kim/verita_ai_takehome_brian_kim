from django.db import models


class AuditLog(models.Model):
    id = models.AutoField(primary_key=True)
    entity_type = models.CharField(max_length=255)
    entity_id = models.CharField(max_length=255)
    action = models.CharField(max_length=255)
    actor = models.CharField(max_length=255)
    before_value = models.JSONField(null=True, blank=True)
    after_value = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Only allow initial save, no updates
        if self.pk is not None:
            raise PermissionError("AuditLog entries cannot be modified")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("AuditLog entries cannot be deleted")

    def __str__(self):
        return f"AuditLog: {self.entity_type} {self.entity_id} - {self.action}"

    class Meta:
        db_table = "audit_logs"


class WebhookDelivery(models.Model):
    id = models.AutoField(primary_key=True)
    external_id = models.CharField(max_length=255, unique=True)
    payload = models.JSONField()
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"WebhookDelivery {self.external_id}"

    class Meta:
        db_table = "webhook_deliveries"
