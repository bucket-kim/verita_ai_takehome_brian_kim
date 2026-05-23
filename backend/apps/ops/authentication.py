import hmac
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class OpsUser:
    """
    Simple internal user object for ops authentication.
    """
    is_authenticated = True
    is_ops = True

    def __str__(self):
        return "OpsUser"


class OpsTokenAuthentication(BaseAuthentication):
    """
    Authentication class for ops endpoints that validates tokens from X-Ops-Token header.

    Compares the provided token against the OPS_TOKEN environment variable
    using hmac.compare_digest to prevent timing attacks.
    """

    def authenticate(self, request):
        ops_token_header = request.META.get('HTTP_X_OPS_TOKEN')

        if not ops_token_header:
            return None

        ops_token = settings.OPS_TOKEN
        if not ops_token:
            raise AuthenticationFailed('Ops authentication not configured')

        # Use hmac.compare_digest to prevent timing attacks
        if not hmac.compare_digest(ops_token_header, ops_token):
            raise AuthenticationFailed('Invalid ops token')

        # Return (user, auth) tuple
        return (OpsUser(), None)
