from django.urls import path
from apps.ops.views import (
    CustomerListView,
    CustomerDetailView,
    CustomerCreditsView,
    InvoiceLineItemUpdateView,
    WebhookPaymentView,
)

urlpatterns = [
    path('ops/customers', CustomerListView.as_view(), name='ops-customer-list'),
    path('ops/customers/<uuid:customer_id>', CustomerDetailView.as_view(), name='ops-customer-detail'),
    path('ops/customers/<uuid:customer_id>/credits', CustomerCreditsView.as_view(), name='ops-customer-credits'),
    path('ops/invoices/<uuid:invoice_id>/line-items/<int:line_item_id>', InvoiceLineItemUpdateView.as_view(), name='ops-invoice-line-item-update'),
    path('webhooks/payments', WebhookPaymentView.as_view(), name='webhook-payments'),
]
