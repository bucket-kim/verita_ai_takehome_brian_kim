import os
from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.billing'

    def ready(self):
        # Only run scheduler in the main process (not in reloader)
        if os.environ.get('RUN_MAIN') == 'true':
            from apscheduler.schedulers.background import BackgroundScheduler
            from apps.billing.jobs import aggregate_usage_windows, generate_invoices

            scheduler = BackgroundScheduler()

            # Run aggregate_usage_windows every 5 minutes
            scheduler.add_job(
                aggregate_usage_windows,
                'interval',
                minutes=5,
                id='aggregate_usage_windows',
                replace_existing=True
            )

            # Run generate_invoices on the 1st of each month at midnight
            scheduler.add_job(
                generate_invoices,
                'cron',
                day=1,
                hour=0,
                minute=0,
                id='generate_invoices',
                replace_existing=True
            )

            scheduler.start()
            print("APScheduler started with jobs: aggregate_usage_windows (every 5min), generate_invoices (monthly)")
