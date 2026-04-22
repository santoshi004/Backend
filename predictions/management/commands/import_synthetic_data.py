import csv
import json
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils.timezone import make_aware
from accounts.models import User
from medications.models import Medication, PatientProfile
from adherence.models import AdherenceLog

class Command(BaseCommand):
    help = 'Import synthetic data from medassist_dataset.csv'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Path to the medassist_dataset.csv file')

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        
        self.stdout.write(f"Reading from {csv_path}...")
        
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            
            # Cache for users and medications to avoid duplicate queries
            user_cache = {}
            med_cache = {}

            # Clear existing data for a fresh start in the lab (Optional, but safer for a clean demo)
            # AdherenceLog.objects.all().delete()
            # Medication.objects.all().delete()
            # User.objects.filter(role='patient').delete()

            for row in reader:
                patient_id_val = row['Patient_ID']
                patient_name = row['Patient_Name']
                med_name = row['Medication_Name']
                dosage = row['Dosage']
                freq = row['Frequency']
                timings_str = row['Timings']
                sched_str = row['Scheduled_Time']
                taken_str = row['Taken_Time']
                status = row['Status']

                # 1. Get or Create Patient
                email = f"{patient_id_val.lower()}@medassist-demo.com"
                if email not in user_cache:
                    user, created = User.objects.get_or_create(
                        email=email,
                        defaults={
                            'name': patient_name,
                            'role': 'patient',
                            'password': 'demo_password_123'
                        }
                    )
                    user_cache[email] = user
                    # Ensure patient is linked to a caretaker (the current one or admin)
                    admin = User.objects.filter(role='caretaker', is_superuser=True).first()
                    if admin:
                        PatientProfile.objects.get_or_create(user=user, caretaker=admin)
                
                patient = user_cache[email]

                # 2. Get or Create Medication
                med_key = (patient.id, med_name)
                if med_key not in med_cache:
                    # Clean the timings JSON
                    try:
                        timings_list = json.loads(timings_str.replace("'", '"'))
                    except:
                        timings_list = ["08:00"]
                    
                    med, created = Medication.objects.get_or_create(
                        patient=patient,
                        name=med_name,
                        defaults={
                            'dosage': dosage,
                            'frequency': freq,
                            'timings': timings_list,
                            'is_active': True
                        }
                    )
                    med_cache[med_key] = med
                
                med = med_cache[med_key]

                # 3. Create Adherence Log
                try:
                    sched_dt = make_aware(datetime.strptime(sched_str, '%Y-%m-%d %H:%M:%S'))
                    taken_dt = None
                    if taken_str and status != 'missed':
                        taken_dt = make_aware(datetime.strptime(taken_str, '%Y-%m-%d %H:%M:%S'))
                    
                    AdherenceLog.objects.create(
                        patient=patient,
                        medication=med,
                        scheduled_time=sched_dt,
                        taken_time=taken_dt,
                        status=status
                    )
                    count += 1
                    if count % 500 == 0:
                        self.stdout.write(f"Imported {count} logs...")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error at row {count}: {e}"))

            self.stdout.write(self.style.SUCCESS(f"Successfully imported {count} adherence records!"))
