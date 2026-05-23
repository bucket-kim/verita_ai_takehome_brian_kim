from django.urls import path
from apps.usage.views import EventsView, UsageView

urlpatterns = [
    path('v1/events', EventsView.as_view(), name='events'),
    path('v1/usage', UsageView.as_view(), name='usage'),
]
