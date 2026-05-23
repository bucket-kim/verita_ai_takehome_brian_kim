from django.urls import path
from apps.billing.views import InvoiceListView, InvoiceDetailView

urlpatterns = [
    path('v1/invoices', InvoiceListView.as_view(), name='invoice-list'),
    path('v1/invoices/<uuid:invoice_id>', InvoiceDetailView.as_view(), name='invoice-detail'),
]
