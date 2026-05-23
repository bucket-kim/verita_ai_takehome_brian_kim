import hashlib
import secrets
import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.customers.models import Customer, ApiKey
from apps.usage.models import UsageEvent
from apps.billing.jobs import aggregate_usage_windows, generate_invoices


class Command(BaseCommand):
    help = 'Seed the database with test data: customers, API keys, and usage events'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting seed process...'))

        # Create 20 customers with API keys
        customers = []
        sample_api_key = None

        for i in range(20):
            customer = Customer.objects.create(
                name=f'Customer {i+1}',
                email=f'customer{i+1}@example.com'
            )
            customers.append(customer)

            # Generate 1-2 API keys per customer
            num_keys = random.randint(1, 2)
            for j in range(num_keys):
                # Generate plaintext API key
                plaintext_key = 'sk_' + secrets.token_hex(24)

                # Hash the key
                key_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
                key_prefix = plaintext_key[:8]

                api_key = ApiKey.objects.create(
                    customer=customer,
                    key_hash=key_hash,
                    key_prefix=key_prefix
                )

                # Save first API key as sample (only time we have plaintext)
                if sample_api_key is None:
                    sample_api_key = {
                        'customer': customer.name,
                        'email': customer.email,
                        'plaintext': plaintext_key,
                        'id': str(api_key.id)
                    }

        self.stdout.write(self.style.SUCCESS(f'Created {len(customers)} customers'))

        # Create a known test API key for easy testing
        test_customer = customers[0]  # Use first customer
        test_key_plaintext = 'sk_test_demo_key_11111111111111111111111111111111'
        test_key_hash = hashlib.sha256(test_key_plaintext.encode()).hexdigest()

        ApiKey.objects.create(
            customer=test_customer,
            key_hash=test_key_hash,
            key_prefix='sk_test_'
        )

        # Print test credentials
        self.stdout.write(self.style.WARNING('\n' + '='*60))
        self.stdout.write(self.style.WARNING('TEST CREDENTIALS FOR LOGIN:'))
        self.stdout.write(self.style.WARNING('='*60))
        self.stdout.write(self.style.SUCCESS('Customer Portal Login:'))
        self.stdout.write(f"  URL: http://localhost:5173/customer/login")
        self.stdout.write(f"  API Key: {test_key_plaintext}")
        self.stdout.write(f"  Customer: {test_customer.name} ({test_customer.email})")
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Ops Console Login:'))
        self.stdout.write(f"  URL: http://localhost:5173/ops/login")
        self.stdout.write(f"  Token: Check your .env file (default: ops-dev-token-12345)")
        self.stdout.write(self.style.WARNING('='*60 + '\n'))

        # Generate ~50,000 usage events over 60 days
        self.stdout.write('Generating usage events...')

        events_to_create = []
        total_events = 50000
        days_back = 60
        now = timezone.now()

        for i in range(total_events):
            # Pick a random customer
            customer = random.choice(customers)
            api_key = random.choice(list(customer.api_keys.all()))

            # Generate timestamp over past 60 days
            # Higher activity during business hours (9am-6pm)
            hours_back = random.randint(0, days_back * 24)
            event_time = now - timedelta(hours=hours_back)

            # Adjust for realistic patterns (higher during business hours)
            hour_of_day = event_time.hour
            if 9 <= hour_of_day <= 18:
                # Business hours - more likely to generate events
                skip_probability = 0.1  # 90% chance to create
            else:
                # Off hours - less likely
                skip_probability = 0.6  # 40% chance to create

            if random.random() < skip_probability:
                continue

            # Some events have timestamps 2-3 hours behind ingestion (late reporting)
            if random.random() < 0.15:  # 15% of events are "late"
                event_time -= timedelta(hours=random.randint(2, 3))

            # Generate request_id
            request_id = f'req_{secrets.token_hex(16)}'

            # Random endpoint
            endpoints = ['/api/chat', '/api/completion', '/api/embedding', '/api/search']
            endpoint = random.choice(endpoints)

            # Random units (1-1000, weighted toward lower values)
            units = int(random.expovariate(1/100)) + 1
            units = min(units, 1000)

            event = UsageEvent(
                request_id=request_id,
                customer=customer,
                api_key=api_key,
                endpoint=endpoint,
                units=units,
                event_timestamp=event_time
            )
            events_to_create.append(event)

            # Bulk create in batches of 1000
            if len(events_to_create) >= 1000:
                UsageEvent.objects.bulk_create(events_to_create, ignore_conflicts=True)
                self.stdout.write(f'  Created {len(events_to_create)} events...')
                events_to_create = []

        # Create remaining events
        if events_to_create:
            UsageEvent.objects.bulk_create(events_to_create, ignore_conflicts=True)

        total_created = UsageEvent.objects.count()
        self.stdout.write(self.style.SUCCESS(f'Generated {total_created} usage events'))

        # Run background jobs
        self.stdout.write('Running aggregate_usage_windows...')
        aggregate_usage_windows()

        self.stdout.write('Running generate_invoices...')
        generate_invoices()

        self.stdout.write(self.style.SUCCESS('\nSeed process completed successfully!'))
        self.stdout.write(f'Total customers: {Customer.objects.count()}')
        self.stdout.write(f'Total API keys: {ApiKey.objects.count()}')
        self.stdout.write(f'Total usage events: {UsageEvent.objects.count()}')
