from django.core.management.base import BaseCommand
from predictions.services.ml_service import train_models

class Command(BaseCommand):
    help = 'Train the ML models for medication adherence prediction'

    def handle(self, *args, **options):
        self.stdout.write("Initializing model training context...")
        success = train_models()
        if success:
            self.stdout.write(self.style.SUCCESS("Successfully trained and saved ML models!"))
        else:
            self.stdout.write(self.style.ERROR("Training failed or not enough data."))
