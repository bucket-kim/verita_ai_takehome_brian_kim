import base64
import hmac
import hashlib
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db.models import Q
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
        from django.db.models import Sum, Q
        from apps.usage.models import UsageEvent

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

        # Calculate this month's usage and outstanding balance for each customer
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        results = []
        for customer in customers:
            # This month's usage
            this_month_usage = UsageEvent.objects.filter(
                customer=customer,
                event_timestamp__gte=month_start
            ).aggregate(total=Sum('units'))['total'] or 0

            # Outstanding balance (unpaid invoices)
            outstanding_balance = Invoice.objects.filter(
                customer=customer,
                status__in=['draft', 'issued']
            ).aggregate(total=Sum('total_cents'))['total'] or 0

            results.append({
                'id': str(customer.id),
                'name': customer.name,
                'email': customer.email,
                'created_at': customer.created_at.isoformat(),
                'this_month_usage': this_month_usage,
                'outstanding_balance_cents': outstanding_balance
            })

        # Generate next cursor
        next_cursor = None
        if has_more and customers:
            last_customer = customers[-1]
            cursor_data = f"{last_customer.created_at.isoformat()}|{last_customer.id}"
            next_cursor = base64.b64encode(cursor_data.encode('utf-8')).decode('utf-8')

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
        from django.db.models import Sum
        from apps.usage.models import UsageWindow
        from apps.customers.models import ApiKey
        from datetime import timedelta

        customer = get_object_or_404(Customer, id=customer_id)

        # API key prefixes
        api_keys = ApiKey.objects.filter(
            customer=customer,
            revoked_at__isnull=True
        ).values_list('key_prefix', flat=True)

        # Usage data for last 30 days (hourly windows)
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        usage_windows = UsageWindow.objects.filter(
            customer=customer,
            window_start__gte=thirty_days_ago
        ).order_by('window_start').values('window_start', 'total_units')

        usage_data = [{
            'timestamp': window['window_start'].isoformat(),
            'units': window['total_units']
        } for window in usage_windows]

        # Invoice list
        invoices = Invoice.objects.filter(
            customer=customer
        ).order_by('-created_at').values(
            'id', 'period_start', 'period_end', 'status', 'total_cents', 'created_at', 'paid_at'
        )

        invoice_list = [{
            'id': str(invoice['id']),
            'period_start': invoice['period_start'].isoformat(),
            'period_end': invoice['period_end'].isoformat(),
            'status': invoice['status'],
            'total_cents': invoice['total_cents'],
            'created_at': invoice['created_at'].isoformat(),
            'paid_at': invoice['paid_at'].isoformat() if invoice['paid_at'] else None
        } for invoice in invoices]

        # Last 5 audit log entries related to this customer
        # Get line item IDs as strings for comparison with entity_id
        line_item_ids = [str(id) for id in InvoiceLineItem.objects.filter(
            invoice__customer=customer
        ).values_list('id', flat=True)]

        audit_logs = AuditLog.objects.filter(
            Q(entity_type='Credit', after_value__customer_id=str(customer_id)) |
            Q(entity_type='InvoiceLineItem', entity_id__in=line_item_ids)
        ).order_by('-created_at')[:5]

        audit_log_list = [{
            'id': log.id,
            'entity_type': log.entity_type,
            'entity_id': log.entity_id,
            'action': log.action,
            'actor': log.actor,
            'reason': log.reason,
            'created_at': log.created_at.isoformat()
        } for log in audit_logs]

        result = {
            'id': str(customer.id),
            'name': customer.name,
            'email': customer.email,
            'created_at': customer.created_at.isoformat(),
            'api_key_prefixes': list(api_keys),
            'usage_data': usage_data,
            'invoices': invoice_list,
            'audit_logs': audit_log_list
        }

        return Response(result)


class CustomerCreditsView(OpsAPIView):
    """
    POST /ops/customers/<uuid:id>/credits - Add credits to a customer.

    Uses select_for_update to prevent concurrent double-credit issues.
    Creates Credit and writes AuditLog entry.
    Supports idempotency via X-Idempotency-Key header.
    """

    def post(self, request, customer_id):
        amount_cents = request.data.get('amount_cents')
        reason = request.data.get('reason', '')
        created_by = request.data.get('created_by', 'ops')
        idempotency_key = request.META.get('HTTP_X_IDEMPOTENCY_KEY')

        if amount_cents is None:
            return Response(
                {'error': 'amount_cents is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not reason:
            return Response(
                {'error': 'reason is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            amount_cents = int(amount_cents)
        except (ValueError, TypeError):
            return Response(
                {'error': 'amount_cents must be an integer'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check for existing credit with same idempotency key
        if idempotency_key:
            existing_credit = Credit.objects.filter(idempotency_key=idempotency_key).first()
            if existing_credit:
                return Response({
                    'id': existing_credit.id,
                    'customer_id': str(existing_credit.customer.id),
                    'amount_cents': existing_credit.amount_cents,
                    'reason': existing_credit.reason,
                    'created_by': existing_credit.created_by,
                    'created_at': existing_credit.created_at.isoformat()
                }, status=status.HTTP_200_OK)

        with transaction.atomic():
            # Lock the customer row to prevent concurrent modifications
            customer = Customer.objects.select_for_update().get(id=customer_id)

            # Create the credit
            credit = Credit.objects.create(
                customer=customer,
                amount_cents=amount_cents,
                reason=reason,
                created_by=created_by,
                idempotency_key=idempotency_key
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

        if not reason:
            return Response(
                {'error': 'reason is required'},
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


class InvoiceDetailView(OpsAPIView):
    """
    GET /ops/invoices/<uuid:id> - Get invoice details with line items.
    """

    def get(self, request, invoice_id):
        invoice = get_object_or_404(Invoice, id=invoice_id)

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
            'customer_id': str(invoice.customer.id),
            'customer_name': invoice.customer.name,
            'period_start': invoice.period_start.isoformat(),
            'period_end': invoice.period_end.isoformat(),
            'status': invoice.status,
            'total_cents': invoice.total_cents,
            'created_at': invoice.created_at.isoformat(),
            'paid_at': invoice.paid_at.isoformat() if invoice.paid_at else None,
            'line_items': line_items
        }

        return Response(result)


class LineItemAuditLogView(OpsAPIView):
    """
    GET /ops/invoices/<uuid:id>/line-items/<int:lid>/audit-logs - Get audit logs for a line item.
    """

    def get(self, request, invoice_id, line_item_id):
        # Verify the line item exists
        line_item = get_object_or_404(
            InvoiceLineItem,
            id=line_item_id,
            invoice_id=invoice_id
        )

        # Get audit logs for this line item
        audit_logs = AuditLog.objects.filter(
            entity_type='InvoiceLineItem',
            entity_id=str(line_item_id)
        ).order_by('-created_at')

        results = [{
            'id': log.id,
            'action': log.action,
            'actor': log.actor,
            'before_value': log.before_value,
            'after_value': log.after_value,
            'reason': log.reason,
            'created_at': log.created_at.isoformat()
        } for log in audit_logs]

        return Response({'audit_logs': results})


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
