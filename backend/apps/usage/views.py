import base64
from datetime import datetime
from rest_framework.response import Response
from rest_framework import status
from django.db import IntegrityError
from apps.customers.views import TenantScopedAPIView
from apps.usage.models import UsageEvent
from apps.customers.models import ApiKey


class EventsView(TenantScopedAPIView):
    """
    POST /v1/events - Bulk insert usage events with idempotency.

    Accepts: {"events": [{request_id, api_key_id, endpoint, units, timestamp}]}
    Returns: 207 with per-event {"request_id": ..., "status": "created"|"duplicate"}
    """

    def post(self, request):
        events_data = request.data.get('events', [])

        if not isinstance(events_data, list):
            return Response(
                {'error': 'events must be a list'},
                status=status.HTTP_400_BAD_REQUEST
            )

        results = []
        events_to_create = []

        for event_data in events_data:
            request_id = event_data.get('request_id')
            api_key_id = event_data.get('api_key_id')
            endpoint = event_data.get('endpoint')
            units = event_data.get('units')
            timestamp = event_data.get('timestamp')

            # Validate required fields
            if not all([request_id, api_key_id, endpoint, units, timestamp]):
                results.append({
                    'request_id': request_id,
                    'status': 'error',
                    'message': 'Missing required fields'
                })
                continue

            # Verify the API key belongs to the customer
            try:
                api_key = ApiKey.objects.get(id=api_key_id, customer=self.customer)
            except ApiKey.DoesNotExist:
                results.append({
                    'request_id': request_id,
                    'status': 'error',
                    'message': 'Invalid api_key_id for this customer'
                })
                continue

            # Parse timestamp
            try:
                if isinstance(timestamp, str):
                    event_timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                else:
                    event_timestamp = timestamp
            except (ValueError, AttributeError):
                results.append({
                    'request_id': request_id,
                    'status': 'error',
                    'message': 'Invalid timestamp format'
                })
                continue

            events_to_create.append(UsageEvent(
                request_id=request_id,
                customer=self.customer,
                api_key=api_key,
                endpoint=endpoint,
                units=units,
                event_timestamp=event_timestamp
            ))

        # Bulk create with ignore_conflicts for idempotency
        if events_to_create:
            created_events = UsageEvent.objects.bulk_create(
                events_to_create,
                ignore_conflicts=True
            )

            # Check which ones were actually created
            created_request_ids = {event.request_id for event in created_events if event.pk}
            all_request_ids = {event.request_id for event in events_to_create}

            for event in events_to_create:
                if event.request_id in created_request_ids:
                    results.append({
                        'request_id': event.request_id,
                        'status': 'created'
                    })
                else:
                    # Check if it already existed
                    if UsageEvent.objects.filter(request_id=event.request_id).exists():
                        results.append({
                            'request_id': event.request_id,
                            'status': 'duplicate'
                        })
                    else:
                        results.append({
                            'request_id': event.request_id,
                            'status': 'created'
                        })

        return Response({'results': results}, status=status.HTTP_207_MULTI_STATUS)


class UsageView(TenantScopedAPIView):
    """
    GET /v1/usage?start=&end=&api_key_id=&cursor=&limit=50
    Query usage events with cursor pagination.
    """

    def get(self, request):
        # Always filter by customer first
        queryset = UsageEvent.objects.filter(customer=self.customer)

        # Filter by date range
        start = request.query_params.get('start')
        end = request.query_params.get('end')
        if start:
            try:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                queryset = queryset.filter(event_timestamp__gte=start_dt)
            except ValueError:
                return Response(
                    {'error': 'Invalid start timestamp format'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if end:
            try:
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                queryset = queryset.filter(event_timestamp__lte=end_dt)
            except ValueError:
                return Response(
                    {'error': 'Invalid end timestamp format'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Filter by api_key_id
        api_key_id = request.query_params.get('api_key_id')
        if api_key_id:
            queryset = queryset.filter(api_key_id=api_key_id)

        # Cursor pagination
        cursor = request.query_params.get('cursor')
        if cursor:
            try:
                decoded = base64.b64decode(cursor).decode('utf-8')
                timestamp_str, event_id = decoded.split('|')
                cursor_timestamp = datetime.fromisoformat(timestamp_str)
                queryset = queryset.filter(
                    event_timestamp__lt=cursor_timestamp
                ) | queryset.filter(
                    event_timestamp=cursor_timestamp,
                    id__lt=event_id
                )
            except (ValueError, IndexError):
                return Response(
                    {'error': 'Invalid cursor'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Limit
        limit = int(request.query_params.get('limit', 50))
        queryset = queryset.order_by('-event_timestamp', '-id')[:limit + 1]

        events = list(queryset)
        has_more = len(events) > limit
        if has_more:
            events = events[:limit]

        # Generate next cursor
        next_cursor = None
        if has_more and events:
            last_event = events[-1]
            cursor_data = f"{last_event.event_timestamp.isoformat()}|{last_event.id}"
            next_cursor = base64.b64encode(cursor_data.encode('utf-8')).decode('utf-8')

        # Serialize events
        results = [{
            'id': str(event.id),
            'request_id': event.request_id,
            'api_key_id': str(event.api_key_id),
            'endpoint': event.endpoint,
            'units': event.units,
            'event_timestamp': event.event_timestamp.isoformat(),
            'ingested_at': event.ingested_at.isoformat()
        } for event in events]

        return Response({
            'events': results,
            'next_cursor': next_cursor,
            'has_more': has_more
        })
