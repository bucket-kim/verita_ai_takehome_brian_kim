#!/bin/bash

echo "=========================================="
echo "Testing Automatic Seeding"
echo "=========================================="
echo ""

echo "Current state check..."
docker compose exec backend python manage.py shell -c "
from apps.customers.models import Customer
print(f'Current customer count: {Customer.objects.count()}')
"

echo ""
echo "----------------------------------------"
echo "Test 1: Restart with existing data"
echo "----------------------------------------"
echo "Running: docker compose down && docker compose up -d"
echo ""

docker compose down
docker compose up -d

echo ""
echo "Waiting for services to start..."
sleep 15

echo ""
echo "Checking logs for seed behavior..."
docker compose logs backend | grep -A 2 "Checking for existing data"

echo ""
echo "Verifying data count..."
docker compose exec backend python manage.py shell -c "
from apps.customers.models import Customer
print(f'Customer count after restart: {Customer.objects.count()}')
"

echo ""
echo "=========================================="
echo "✓ Test Complete"
echo "=========================================="
echo ""
echo "To test FRESH database auto-seed:"
echo "  1. Run: docker compose down -v"
echo "  2. Run: docker compose up"
echo "  3. Watch logs for full seed process"
