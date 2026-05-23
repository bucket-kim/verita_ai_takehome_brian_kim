from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from apps.customers.views import TenantScopedAPIView
from apps.billing.models import Invoice


class InvoiceListView(TenantScopedAPIView):
    """
    GET /v1/invoices - List invoices for the authenticated customer only.
    """

    def get(self, request):
        invoices = Invoice.objects.filter(customer=self.customer).order_by('-created_at')

        results = [{
            'id': str(invoice.id),
            'period_start': invoice.period_start.isoformat(),
            'period_end': invoice.period_end.isoformat(),
            'status': invoice.status,
            'total_cents': invoice.total_cents,
            'created_at': invoice.created_at.isoformat(),
            'paid_at': invoice.paid_at.isoformat() if invoice.paid_at else None
        } for invoice in invoices]

        return Response({'invoices': results})


class InvoiceDetailView(TenantScopedAPIView):
    """
    GET /v1/invoices/<uuid:id> - Get invoice details with line items.

    Uses get_object_or_404 with customer filter to prevent cross-tenant access.
    """

    def get(self, request, invoice_id):
        # The customer filter prevents cross-tenant access
        invoice = get_object_or_404(Invoice, id=invoice_id, customer=self.customer)

        line_items = [{
            'id': item.id,
            'description': item.description,
            'units': item.units,
            'unit_price_millicents': item.unit_price_millicents,
            'total_cents': item.total_cents,
            'overridden': item.overridden
        } for item in invoice.line_items.all()]

        result = {
            'id': str(invoice.id),
            'period_start': invoice.period_start.isoformat(),
            'period_end': invoice.period_end.isoformat(),
            'status': invoice.status,
            'total_cents': invoice.total_cents,
            'created_at': invoice.created_at.isoformat(),
            'paid_at': invoice.paid_at.isoformat() if invoice.paid_at else None,
            'line_items': line_items
        }

        return Response(result)
