"""
Development settings.
"""
from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

# CORS settings for development
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-api-key',
    'x-ops-token',
    'x-idempotency-key',
]
