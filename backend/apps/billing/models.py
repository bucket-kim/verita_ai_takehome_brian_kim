import uuid
from django.db import models


class PricePlan(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    tiers = models.JSONField()  # Array of {up_to, unit_price_millicents}

    def __str__(self):
        return self.name

    class Meta:
        db_table = "price_plans"


class Invoice(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("issued", "Issued"),
        ("paid", "Paid"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="invoices"
    )
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    total_cents = models.IntegerField()  # Money in cents
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Invoice {self.id} - {self.customer.name} - ${self.total_cents / 100:.2f}"

    class Meta:
        db_table = "invoices"
        indexes = [
            models.Index(fields=["customer", "status"]),
        ]


class InvoiceLineItem(models.Model):
    id = models.AutoField(primary_key=True)
    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="line_items"
    )
    description = models.CharField(max_length=255)
    units = models.IntegerField()
    unit_price_millicents = models.IntegerField()  # Price per unit in millicents
    total_cents = models.IntegerField()  # Total in cents
    overridden = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.description} - {self.units} units"

    class Meta:
        db_table = "invoice_line_items"


class Credit(models.Model):
    id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="credits"
    )
    amount_cents = models.IntegerField()  # Money in cents
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=255)

    def __str__(self):
        return f"Credit for {self.customer.name} - ${self.amount_cents / 100:.2f}"

    class Meta:
        db_table = "credits"
