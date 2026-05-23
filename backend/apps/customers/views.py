from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated


class TenantScopedAPIView(APIView):
    """
    Base class for all /v1 customer-facing views.

    Automatically sets self.customer to request.user (the resolved Customer)
    in initial() method. This ensures tenant scoping is applied consistently
    across all customer-facing endpoints without repeating the logic per view.
    """
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # request.user is the Customer instance returned by ApiKeyAuthentication
        self.customer = request.user
