import time
import signal
import sys
from django.core.management.base import BaseCommand
from adherence.utils.notifications import check_and_trigger_reminders

class Command(BaseCommand):
    help = 'Checks for due/missed medications and sends voice/push alerts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--loop',
            action='store_true',
            help='Run in a continuous loop every 60 seconds',
        )

    def handle(self, *args, **options):
        is_looping = options.get('loop')
        
        if is_looping:
            self.stdout.write(self.style.SUCCESS("--- MedAssist AI Voice Monitor Started ---"))
            self.stdout.write("Listening for medication schedules in real-time...")
            
            # Handle Ctrl+C gracefully
            def signal_handler(sig, frame):
                self.stdout.write(self.style.WARNING("\nStopping monitor..."))
                sys.exit(0)
            signal.signal(signal_event := signal.SIGINT, signal_handler)

            while True:
                results = check_and_trigger_reminders()
                for res in results:
                    self.stdout.write(self.style.SUCCESS(f"[{time.strftime('%H:%M:%S')}] {res}"))
                time.sleep(60)
        else:
            self.stdout.write("Checking medication reminders (One-time)...")
            results = check_and_trigger_reminders()
            for res in results:
                self.stdout.write(self.style.SUCCESS(res))
            self.stdout.write(f"Done. Sent {len(results)} alerts.")
