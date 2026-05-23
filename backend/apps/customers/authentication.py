import hashlib
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from apps.customers.models import ApiKey


class ApiKeyAuthentication(BaseAuthentication):
    """
    Authentication class that validates API keys from X-API-Key header.

    Hashes the provided key with SHA256 and looks up the ApiKey by key_hash
    where revoked_at is null. Returns (api_key.customer, api_key).
    Never returns the plaintext key.
    """

    def authenticate(self, request):
        api_key_header = request.META.get('HTTP_X_API_KEY')

        if not api_key_header:
            return None

        # Hash the provided key
        key_hash = hashlib.sha256(api_key_header.encode()).hexdigest()

        # Look up the API key
        try:
            api_key = ApiKey.objects.select_related('customer').get(
                key_hash=key_hash,
                revoked_at__isnull=True
            )
        except ApiKey.DoesNotExist:
            raise AuthenticationFailed('Invalid or revoked API key')

        # Return (user, auth) tuple - customer is the "user"
        return (api_key.customer, api_key)
