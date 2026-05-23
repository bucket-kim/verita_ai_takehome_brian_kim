#!/bin/bash
# Start the Metered Billing System and display login credentials

echo "Starting Metered Billing System..."
echo ""

# Start services
docker-compose up -d

echo ""
echo "Waiting for services to initialize..."
echo "(This may take 10-15 seconds for first-time setup with data seeding)"
echo ""

# Wait for backend to be ready
MAX_WAIT=60
COUNTER=0
while [ $COUNTER -lt $MAX_WAIT ]; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/v1/invoices -H "X-API-Key: sk_test_demo_key_11111111111111111111111111111111" | grep -q "200"; then
        break
    fi
    echo -n "."
    sleep 2
    COUNTER=$((COUNTER + 2))
done

echo ""
echo ""

# Display credentials
./show_credentials.sh

# Show the open_localhost.txt content
echo ""
cat open_localhost.txt

echo ""
echo "✅ System is ready! Use the credentials above to login."
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
echo ""
echo "To stop services:"
echo "  docker-compose down"
echo ""
