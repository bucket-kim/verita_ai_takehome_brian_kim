import base64
import hmac
import hashlib
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from apps.ops.authentication import OpsTokenAuthentication
from apps.customers.models import Customer
from apps.billing.models import Credit, Invoice, InvoiceLineItem
from apps.ops.models import AuditLog, WebhookDelivery


class OpsAPIView(APIView):
    """
    Base class for ops endpoints that require OpsTokenAuthentication.
    """
    authentication_classes = [OpsTokenAuthentication]
    permission_classes = [IsAuthenticated]


class CustomerListView(OpsAPIView):
    """
    GET /ops/customers?cursor=&limit=50 - List all customers with cursor pagination.
    """

    def get(self, request):
        queryset = Customer.objects.all().order_by('-created_at', '-id')

        # Cursor pagination
        cursor = request.query_params.get('cursor')
        if cursor:
            try:
                decoded = base64.b64decode(cursor).decode('utf-8')
                timestamp_str, customer_id = decoded.split('|')
                cursor_timestamp = datetime.fromisoformat(timestamp_str)
                queryset = queryset.filter(
                    created_at__lt=cursor_timestamp
                ) | queryset.filter(
                    created_at=cursor_timestamp,
                    id__lt=customer_id
                )
            except (ValueError, IndexError):
                return Response(
                    {'error': 'Invalid cursor'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Limit
        limit = int(request.query_params.get('limit', 50))
        customers = list(queryset[:limit + 1])

        has_more = len(customers) > limit
        if has_more:
            customers = customers[:limit]

        # Generate next cursor
        next_cursor = None
        if has_more and customers:
            last_customer = customers[-1]
            cursor_data = f"{last_customer.created_at.isoformat()}|{last_customer.id}"
            next_cursor = base64.b64encode(cursor_data.encode('utf-8')).decode('utf-8')

        results = [{
            'id': str(customer.id),
            'name': customer.name,
            'email': customer.email,
            'created_at': customer.created_at.isoformat()
        } for customer in customers]

        return Response({
            'customers': results,
            'next_cursor': next_cursor,
            'has_more': has_more
        })


class CustomerDetailView(OpsAPIView):
    """
    GET /ops/customers/<uuid:id> - Get customer details.
    """

    def get(self, request, customer_id):
        customer = get_object_or_404(Customer, id=customer_id)

        result = {
            'id': str(customer.id),
            'name': customer.name,
            'email': customer.email,
            'created_at': customer.created_at.isoformat()
        }

        return Response(result)


class CustomerCreditsView(OpsAPIView):
    """
    POST /ops/customers/<uuid:id>/credits - Add credits to a customer.

    Uses select_for_update to prevent concurrent double-credit issues.
    Creates Credit and writes AuditLog entry.
    """

    def post(self, request, customer_id):
        amount_cents = request.data.get('amount_cents')
        reason = request.data.get('reason', '')
        created_by = request.data.get('created_by', 'ops')

        if amount_cents is None:
            return Response(
                {'error': 'amount_cents is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            amount_cents = int(amount_cents)
        except (ValueError, TypeError):
            return Response(
                {'error': 'amount_cents must be an integer'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            # Lock the customer row to prevent concurrent modifications
            customer = Customer.objects.select_for_update().get(id=customer_id)

            # Create the credit
            credit = Credit.objects.create(
                customer=customer,
                amount_cents=amount_cents,
                reason=reason,
                created_by=created_by
            )

            # Write audit log
            actor = str(request.user) if hasattr(request, 'user') else 'ops'
            AuditLog.objects.create(
                entity_type='Credit',
                entity_id=str(credit.id),
                action='created',
                actor=actor,
                before_value=None,
                after_value={'amount_cents': amount_cents, 'customer_id': str(customer_id)},
                reason=reason
            )

        result = {
            'id': credit.id,
            'customer_id': str(customer.id),
            'amount_cents': credit.amount_cents,
            'reason': credit.reason,
            'created_by': credit.created_by,
            'created_at': credit.created_at.isoformat()
        }

        return Response(result, status=status.HTTP_201_CREATED)


class InvoiceLineItemUpdateView(OpsAPIView):
    """
    PATCH /ops/invoices/<uuid:id>/line-items/<uuid:lid> - Update line item.

    Body: {total_cents, reason}
    Writes AuditLog with before/after values.
    """

    def patch(self, request, invoice_id, line_item_id):
        total_cents = request.data.get('total_cents')
        reason = request.data.get('reason', '')

        if total_cents is None:
            return Response(
                {'error': 'total_cents is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            total_cents = int(total_cents)
        except (ValueError, TypeError):
            return Response(
                {'error': 'total_cents must be an integer'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            line_item = get_object_or_404(
                InvoiceLineItem,
                id=line_item_id,
                invoice_id=invoice_id
            )

            old_total_cents = line_item.total_cents

            # Update the line item
            line_item.total_cents = total_cents
            line_item.overridden = True
            line_item.save()

            # Write audit log
            actor = str(request.user) if hasattr(request, 'user') else 'ops'
            AuditLog.objects.create(
                entity_type='InvoiceLineItem',
                entity_id=str(line_item.id),
                action='updated',
                actor=actor,
                before_value={'total_cents': old_total_cents},
                after_value={'total_cents': total_cents},
                reason=reason
            )

            # Update invoice total
            invoice = line_item.invoice
            invoice.total_cents = sum(item.total_cents for item in invoice.line_items.all())
            invoice.save()

        result = {
            'id': line_item.id,
            'invoice_id': str(invoice_id),
            'description': line_item.description,
            'units': line_item.units,
            'unit_price_millicents': line_item.unit_price_millicents,
            'total_cents': line_item.total_cents,
            'overridden': line_item.overridden
        }

        return Response(result)


@method_decorator(csrf_exempt, name='dispatch')
class WebhookPaymentView(APIView):
    """
    POST /webhooks/payments - Process payment webhook.

    Verifies HMAC-SHA256 signature and updates invoice status to 'paid'.
    Uses get_or_create for idempotency based on external_id.
    """
    authentication_classes = []  # No authentication, uses webhook signature

    def post(self, request):
        # Get the signature from header
        signature = request.META.get('HTTP_X_WEBHOOK_SIGNATURE')
        if not signature:
            return Response(
                {'error': 'Missing webhook signature'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get the raw body for signature verification
        body = request.body
        webhook_secret = settings.WEBHOOK_SECRET

        # Compute expected signature
        expected_signature = hmac.new(
            webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        # Use hmac.compare_digest to prevent timing attacks
        if not hmac.compare_digest(signature, expected_signature):
            return Response(
                {'error': 'Invalid webhook signature'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Parse the payload
        data = request.data
        external_id = data.get('external_id')
        invoice_id = data.get('invoice_id')

        if not external_id or not invoice_id:
            return Response(
                {'error': 'Missing required fields: external_id, invoice_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Idempotency check: skip if already processed
        webhook_delivery, created = WebhookDelivery.objects.get_or_create(
            external_id=external_id,
            defaults={
                'payload': data,
                'processed_at': timezone.now()
            }
        )

        if not created:
            # Already processed
            return Response({'status': 'already_processed'}, status=status.HTTP_200_OK)

        # Process the payment
        try:
            with transaction.atomic():
                invoice = Invoice.objects.get(id=invoice_id)
                invoice.status = 'paid'
                invoice.paid_at = timezone.now()
                invoice.save()

                # Update the webhook delivery
                webhook_delivery.processed_at = timezone.now()
                webhook_delivery.save()

            return Response({'status': 'processed'}, status=status.HTTP_200_OK)

        except Invoice.DoesNotExist:
            return Response(
                {'error': 'Invoice not found'},
                status=status.HTTP_404_NOT_FOUND
            )
