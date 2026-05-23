#!/bin/bash
set -e

echo "=========================================="
echo "Starting Metered Billing System"
echo "=========================================="

# Wait for postgres to be ready
echo "Waiting for postgres..."
while ! pg_isready -h postgres -U postgres > /dev/null 2>&1; do
  sleep 1
done
echo "✓ Postgres is ready"

# Run migrations
echo ""
echo "Running database migrations..."
python manage.py migrate --noinput
echo "✓ Migrations complete"

# Check if seed data exists
echo ""
echo "Checking for existing data..."
CUSTOMER_COUNT=$(python manage.py shell -c "from apps.customers.models import Customer; print(Customer.objects.count())" 2>/dev/null || echo "0")

if [ "$CUSTOMER_COUNT" = "0" ]; then
  echo "No data found. Running seed script..."
  python manage.py seed
  echo "✓ Seed data created"
else
  echo "✓ Found $CUSTOMER_COUNT customers (skipping seed)"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║                            🎉 SYSTEM READY! 🎉                            ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "📍 Services Running:"
echo "   • Frontend:    http://localhost:5173"
echo "   • Backend API: http://localhost:8000"
echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║                         🔐 LOGIN CREDENTIALS                               ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "┌─────────────────────────────────────────────────────────────────────────┐"
echo "│  📱 CUSTOMER PORTAL                                                     │"
echo "├─────────────────────────────────────────────────────────────────────────┤"
echo "│  URL:     http://localhost:5173/customer/login                          │"
echo "│  API Key: sk_test_demo_key_11111111111111111111111111111111             │"
echo "└─────────────────────────────────────────────────────────────────────────┘"
echo ""
echo "┌─────────────────────────────────────────────────────────────────────────┐"
echo "│  🔧 OPS CONSOLE                                                         │"
echo "├─────────────────────────────────────────────────────────────────────────┤"
echo "│  URL:   http://localhost:5173/ops/login                                 │"
echo "│  Token: ${OPS_TOKEN:-ops-dev-token-12345}                               │"
echo "└─────────────────────────────────────────────────────────────────────────┘"
echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║  💡 TIP: Copy these credentials to login to the portals above             ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Start Django development server
exec python manage.py runserver 0.0.0.0:8000
