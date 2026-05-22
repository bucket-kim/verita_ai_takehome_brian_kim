"""
URL configuration for the metered API billing system.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/customers/', include('apps.customers.urls')),
    path('api/usage/', include('apps.usage.urls')),
    path('api/billing/', include('apps.billing.urls')),
    path('api/ops/', include('apps.ops.urls')),
]
