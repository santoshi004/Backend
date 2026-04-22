from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from adherence.models import AdherenceLog

class Command(BaseCommand):
    help = 'Shift adherence log dates for synthetic patients to end at today'

    def handle(self, *args, **options):
        # Target only synthetic patients
        logs = AdherenceLog.objects.filter(patient__email__contains='medassist-demo')
        
        if not logs.exists():
            self.stdout.write(self.style.WARNING("No logs found for synthetic patients (medassist-demo)."))
            return

        latest_log = logs.order_by('-scheduled_time').first()
        latest_date = latest_log.scheduled_time
        today = timezone.now()

        # Calculate offset to bring the latest log to 'today'
        offset = today - latest_date
        # Round offset to days to keep the time-of-day logic consistent
        offset_days = offset.days
        
        self.stdout.write(f"Shifting {logs.count()} logs forward by {offset_days} days...")
        
        # We perform the update
        # Note: We use a loop instead of .update() because scheduled_time is a DateTimeField 
        # and F() expressions with intervals vary by DB engine.
        count = 0
        for log in logs:
            log.scheduled_time += timedelta(days=offset_days)
            if log.taken_time:
                log.taken_time += timedelta(days=offset_days)
            log.save()
            count += 1
            if count % 1000 == 0:
                self.stdout.write(f"Updated {count} records...")

        self.stdout.write(self.style.SUCCESS(f"Successfully shifted {count} logs to the current date range!"))
