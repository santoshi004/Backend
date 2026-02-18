"""
Management command to generate synthetic adherence data for ML training.

Usage:
    python manage.py generate_training_data
    python manage.py generate_training_data --patients 10 --days 60
"""

import random
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from adherence.models import AdherenceLog
from medications.models import Medication, PatientProfile


class Command(BaseCommand):
    help = 'Generate synthetic adherence data for ML model training'

    def add_arguments(self, parser):
        parser.add_argument(
            '--patients',
            type=int,
            default=10,
            help='Number of synthetic patients to create (default: 10)',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days of historical data (default: 30)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing synthetic data before generating',
        )

    def handle(self, *args, **options):
        num_patients = options['patients']
        num_days = options['days']
        clear = options['clear']

        if clear:
            self.stdout.write('Clearing existing synthetic data...')
            User.objects.filter(email__startswith='synthetic_').delete()

        # Create a synthetic caretaker
        caretaker, _ = User.objects.get_or_create(
            email='synthetic_caretaker@medassist.dev',
            defaults={
                'name': 'Synthetic Caretaker',
                'role': 'caretaker',
            },
        )
        if not caretaker.has_usable_password():
            caretaker.set_password('testpass123')
            caretaker.save()

        medications_data = [
            {'name': 'Metformin', 'dosage': '500mg', 'frequency': 'twice_daily', 'timings': ['08:00', '20:00']},
            {'name': 'Lisinopril', 'dosage': '10mg', 'frequency': 'once_daily', 'timings': ['09:00']},
            {'name': 'Atorvastatin', 'dosage': '20mg', 'frequency': 'once_daily', 'timings': ['21:00']},
            {'name': 'Amoxicillin', 'dosage': '500mg', 'frequency': 'thrice_daily', 'timings': ['08:00', '14:00', '20:00']},
            {'name': 'Omeprazole', 'dosage': '20mg', 'frequency': 'once_daily', 'timings': ['07:00']},
            {'name': 'Amlodipine', 'dosage': '5mg', 'frequency': 'once_daily', 'timings': ['10:00']},
            {'name': 'Metoprolol', 'dosage': '50mg', 'frequency': 'twice_daily', 'timings': ['08:00', '20:00']},
        ]

        # Adherence profiles: probability of taking on time, late, or missing
        profiles = [
            {'name': 'excellent', 'taken': 0.90, 'late': 0.08, 'missed': 0.02, 'max_delay': 15},
            {'name': 'good', 'taken': 0.75, 'late': 0.15, 'missed': 0.10, 'max_delay': 30},
            {'name': 'moderate', 'taken': 0.55, 'late': 0.20, 'missed': 0.25, 'max_delay': 60},
            {'name': 'poor', 'taken': 0.30, 'late': 0.15, 'missed': 0.55, 'max_delay': 120},
        ]

        total_logs = 0

        for i in range(num_patients):
            # Create patient
            patient, created = User.objects.get_or_create(
                email=f'synthetic_patient_{i}@medassist.dev',
                defaults={
                    'name': f'Synthetic Patient {i}',
                    'role': 'patient',
                },
            )
            if not patient.has_usable_password():
                patient.set_password('testpass123')
                patient.save()

            # Create patient profile
            PatientProfile.objects.get_or_create(
                user=patient,
                defaults={
                    'age': random.randint(25, 80),
                    'medical_conditions': random.choice([
                        'Type 2 Diabetes',
                        'Hypertension',
                        'High Cholesterol',
                        'Type 2 Diabetes, Hypertension',
                        'Asthma',
                    ]),
                    'caretaker': caretaker,
                },
            )

            # Assign 2-3 medications
            patient_meds = random.sample(medications_data, k=random.randint(2, 3))
            profile = random.choice(profiles)

            for med_data in patient_meds:
                med, _ = Medication.objects.get_or_create(
                    name=med_data['name'],
                    patient=patient,
                    defaults={
                        'dosage': med_data['dosage'],
                        'frequency': med_data['frequency'],
                        'timings': med_data['timings'],
                        'created_by': caretaker,
                        'is_active': True,
                    },
                )

                # Generate adherence logs
                today = timezone.now().date()
                for day_offset in range(num_days, 0, -1):
                    log_date = today - timedelta(days=day_offset)
                    for timing_str in med_data['timings']:
                        hour, minute = map(int, timing_str.split(':'))
                        scheduled_dt = timezone.make_aware(
                            datetime.combine(log_date, time(hour, minute))
                        )

                        roll = random.random()
                        if roll < profile['taken']:
                            # Taken on time (within 5 min)
                            delay_min = random.randint(0, 5)
                            taken_dt = scheduled_dt + timedelta(minutes=delay_min)
                            log_status = 'taken'
                        elif roll < profile['taken'] + profile['late']:
                            # Taken late
                            delay_min = random.randint(15, profile['max_delay'])
                            taken_dt = scheduled_dt + timedelta(minutes=delay_min)
                            log_status = 'late'
                        else:
                            # Missed
                            taken_dt = None
                            log_status = 'missed'

                        AdherenceLog.objects.create(
                            medication=med,
                            patient=patient,
                            scheduled_time=scheduled_dt,
                            taken_time=taken_dt,
                            status=log_status,
                        )
                        total_logs += 1

            self.stdout.write(
                f'  Created patient {i}: {patient.name} ({profile["name"]} adherence)'
            )

        self.stdout.write(self.style.SUCCESS(
            f'\nGenerated {total_logs} adherence logs for {num_patients} patients.'
        ))
        self.stdout.write(
            'Run "python manage.py generate_training_data" again with --clear to reset.'
        )
