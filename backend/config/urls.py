"""
URL configuration for the metered API billing system.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.usage.urls')),
    path('', include('apps.billing.urls')),
    path('', include('apps.ops.urls')),
]
