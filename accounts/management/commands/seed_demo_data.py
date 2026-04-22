import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from accounts.models import User
from medications.models import PatientProfile, Medication
from adherence.models import AdherenceLog
from predictions.models import Prediction
from predictions.services.ml_service import train_models

class Command(BaseCommand):
    help = 'Wipe database and seed 2 Doctors and 6 Patients with unique behaviors. Skips TODAY for demo.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('WIPING ALL DATA...'))
        
        with transaction.atomic():
            AdherenceLog.objects.all().delete()
            Prediction.objects.all().delete()
            Medication.objects.all().delete()
            PatientProfile.objects.all().delete()
            User.objects.all().delete()

            PASSWORD = 'MedAssist2026!'
            NOW = timezone.now().replace(hour=20, minute=0, second=0, microsecond=0)

            # 1. Create Doctors
            dr_smith = User.objects.create_user(
                email='dr.smith@medassist.com', password=PASSWORD,
                name='Dr. Robert Smith', role='caretaker'
            )
            dr_miller = User.objects.create_user(
                email='dr.miller@medassist.com', password=PASSWORD,
                name='Dr. Sarah Miller', role='caretaker'
            )

            # Configuration for the 6 Patients
            patients_conf = [
                # Doctor 1 (Smith)
                {'email': 'p1@medassist.com', 'name': 'Alice (Star Student)', 'doctor': dr_smith, 'behavior': 'star'},
                {'email': 'p2@medassist.com', 'name': 'Bob (Weekend Socialite)', 'doctor': dr_smith, 'behavior': 'weekend'},
                {'email': 'p3@medassist.com', 'name': 'Charlie (Morning Rusher)', 'doctor': dr_smith, 'behavior': 'rusher'},
                # Doctor 2 (Miller)
                {'email': 'p4@medassist.com', 'name': 'David (Recoverer)', 'doctor': dr_miller, 'behavior': 'recoverer'},
                {'email': 'p5@medassist.com', 'name': 'Eve (Forgetter)', 'doctor': dr_miller, 'behavior': 'forgetter'},
                {'email': 'p6@medassist.com', 'name': 'Frank (Lagger)', 'doctor': dr_miller, 'behavior': 'lagger'},
            ]

            for p_info in patients_conf:
                user = User.objects.create_user(
                    email=p_info['email'], password=PASSWORD,
                    name=p_info['name'], role='patient'
                )
                PatientProfile.objects.create(
                    user=user, caretaker=p_info['doctor'], age=random.randint(25, 75),
                    medical_conditions="Demo Condition"
                )

                # Each patient gets 2 Medications (8 AM and 8 PM)
                med1 = Medication.objects.create(
                    name='Lisinopril', dosage='10mg', frequency='twice_daily',
                    timings=['08:00', '20:00'], patient=user, created_by=p_info['doctor']
                )
                med2 = Medication.objects.create(
                    name='Metformin', dosage='500mg', frequency='twice_daily',
                    timings=['08:00', '20:00'], patient=user, created_by=p_info['doctor']
                )

                # Generate 90 days of logs (skipping today)
                self.stdout.write(f'Generating logs for {p_info["email"]} ({p_info["behavior"]})...')
                self.generate_behavioral_logs(user, [med1, med2], p_info['behavior'], NOW)

        self.stdout.write(self.style.SUCCESS('Data Seeding Complete!'))
        self.stdout.write(self.style.WARNING('Retraining ML Models...'))
        train_models()
        self.stdout.write(self.style.SUCCESS('Models Retrained! Dashboard Ready.'))

    def generate_behavioral_logs(self, patient, medications, behavior, now):
        logs = []
        for day in range(1, 91):  # Start from 1 to skip Day 0 (Today)
            current_date = (now - timedelta(days=day)).date()
            
            for med in medications:
                for time_str in med.timings:
                    hour, minute = map(int, time_str.split(':'))
                    scheduled_time = timezone.make_aware(
                        timezone.datetime.combine(current_date, timezone.datetime.min.time().replace(hour=hour, minute=minute))
                    )
                    
                    # behavioral logic
                    status = 'taken'
                    taken_time = scheduled_time + timedelta(minutes=random.randint(-15, 15))

                    if behavior == 'star':
                        # Perfect adherence
                        pass 

                    elif behavior == 'weekend':
                        # Fails Sat (5) and Sun (6)
                        if scheduled_time.weekday() in [5, 6]:
                            status = 'missed'
                            taken_time = None

                    elif behavior == 'rusher':
                        # Fails 8 AM dose specifically
                        if hour < 12:
                            if random.random() < 0.8: # 80% failure rate for morning
                                status = 'missed'
                                taken_time = None

                    elif behavior == 'recoverer':
                        # Improving over time (90 days ago was Day 0)
                        success_rate = 0.2 + (0.7 * (90 - day) / 90) # Starts low, ends high
                        if random.random() > success_rate:
                            status = 'missed'
                            taken_time = None

                    elif behavior == 'forgetter':
                        # Random 40% miss rate
                        if random.random() < 0.4:
                            status = 'missed'
                            taken_time = None

                    elif behavior == 'lagger':
                        # Always 6 hours late
                        status = 'late'
                        taken_time = scheduled_time + timedelta(hours=6, minutes=random.randint(0, 30))

                    logs.append(AdherenceLog(
                        medication=med, patient=patient,
                        scheduled_time=scheduled_time, taken_time=taken_time,
                        status=status, created_at=scheduled_time
                    ))

        # Bulk create for performance
        AdherenceLog.objects.bulk_create(logs)
