from django.core.management.base import BaseCommand
from adherence.utils.notifications import check_and_trigger_reminders

class Command(BaseCommand):
    help = 'Checks for due/missed medications and sends voice/push alerts'

    def handle(self, *args, **options):
        self.stdout.write("Checking medication reminders...")
        results = check_and_trigger_reminders()
        for res in results:
            self.stdout.write(self.style.SUCCESS(res))
        self.stdout.write(f"Done. Sent {len(results)} alerts.")
