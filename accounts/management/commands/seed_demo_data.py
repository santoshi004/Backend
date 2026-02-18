"""
Management command to seed demo data for MedAssist.

Creates:
- 2 caretakers
- 5 patients (linked to caretakers)
- 2-4 medications per patient
- 30 days of adherence logs (mix of taken/missed/late)
- A few prescriptions with sample extracted data
- ML predictions for all patients

Usage:
    python manage.py seed_demo_data
    python manage.py seed_demo_data --clear
"""

import random
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from adherence.models import AdherenceLog
from medications.models import Medication, PatientProfile
from predictions.models import Prediction
from predictions.services.ml_service import generate_predictions_for_patient, train_models
from prescriptions.models import Prescription


DEMO_PASSWORD = 'MedAssist2026!'


class Command(BaseCommand):
    help = 'Seed demo data for MedAssist application'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all existing data before seeding',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing data...')
            Prediction.objects.all().delete()
            Prescription.objects.all().delete()
            AdherenceLog.objects.all().delete()
            Medication.objects.all().delete()
            PatientProfile.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()
            self.stdout.write(self.style.SUCCESS('  Data cleared.'))

        # Create caretakers
        self.stdout.write('\nCreating caretakers...')
        caretakers = []
        caretaker_data = [
            {'email': 'dr.smith@medassist.com', 'name': 'Dr. Robert Smith', 'phone': '+1-555-0101'},
            {'email': 'dr.patel@medassist.com', 'name': 'Dr. Priya Patel', 'phone': '+1-555-0102'},
        ]
        for data in caretaker_data:
            user, created = User.objects.get_or_create(
                email=data['email'],
                defaults={
                    'name': data['name'],
                    'phone': data['phone'],
                    'role': 'caretaker',
                },
            )
            if created or not user.has_usable_password():
                user.set_password(DEMO_PASSWORD)
                user.save()
            caretakers.append(user)
            status = 'created' if created else 'exists'
            self.stdout.write(f'  [{status}] {user.name} ({user.email})')

        # Create patients
        self.stdout.write('\nCreating patients...')
        patient_data = [
            {
                'email': 'john.doe@example.com',
                'name': 'John Doe',
                'phone': '+1-555-0201',
                'age': 65,
                'conditions': 'Type 2 Diabetes, Hypertension',
                'caretaker': caretakers[0],
            },
            {
                'email': 'mary.johnson@example.com',
                'name': 'Mary Johnson',
                'phone': '+1-555-0202',
                'age': 72,
                'conditions': 'High Cholesterol, Osteoarthritis',
                'caretaker': caretakers[0],
            },
            {
                'email': 'james.wilson@example.com',
                'name': 'James Wilson',
                'phone': '+1-555-0203',
                'age': 58,
                'conditions': 'Hypertension',
                'caretaker': caretakers[0],
            },
            {
                'email': 'sarah.brown@example.com',
                'name': 'Sarah Brown',
                'phone': '+1-555-0204',
                'age': 45,
                'conditions': 'Asthma, Allergies',
                'caretaker': caretakers[1],
            },
            {
                'email': 'david.lee@example.com',
                'name': 'David Lee',
                'phone': '+1-555-0205',
                'age': 80,
                'conditions': 'Type 2 Diabetes, Heart Disease, Hypertension',
                'caretaker': caretakers[1],
            },
        ]

        patients = []
        for data in patient_data:
            user, created = User.objects.get_or_create(
                email=data['email'],
                defaults={
                    'name': data['name'],
                    'phone': data['phone'],
                    'role': 'patient',
                },
            )
            if created or not user.has_usable_password():
                user.set_password(DEMO_PASSWORD)
                user.save()

            profile, _ = PatientProfile.objects.get_or_create(
                user=user,
                defaults={
                    'age': data['age'],
                    'medical_conditions': data['conditions'],
                    'caretaker': data['caretaker'],
                },
            )

            patients.append(user)
            status = 'created' if created else 'exists'
            self.stdout.write(
                f'  [{status}] {user.name} ({user.email}) -> {data["caretaker"].name}'
            )

        # Create medications
        self.stdout.write('\nCreating medications...')
        medication_pool = [
            {'name': 'Metformin', 'dosage': '500mg', 'frequency': 'twice_daily', 'timings': ['08:00', '20:00'], 'instructions': 'Take with meals'},
            {'name': 'Lisinopril', 'dosage': '10mg', 'frequency': 'once_daily', 'timings': ['09:00'], 'instructions': 'Take in the morning'},
            {'name': 'Atorvastatin', 'dosage': '20mg', 'frequency': 'once_daily', 'timings': ['21:00'], 'instructions': 'Take at bedtime'},
            {'name': 'Amlodipine', 'dosage': '5mg', 'frequency': 'once_daily', 'timings': ['10:00'], 'instructions': 'Take with or without food'},
            {'name': 'Omeprazole', 'dosage': '20mg', 'frequency': 'once_daily', 'timings': ['07:30'], 'instructions': 'Take before breakfast on empty stomach'},
            {'name': 'Metoprolol', 'dosage': '50mg', 'frequency': 'twice_daily', 'timings': ['08:00', '20:00'], 'instructions': 'Take with food'},
            {'name': 'Aspirin', 'dosage': '81mg', 'frequency': 'once_daily', 'timings': ['08:00'], 'instructions': 'Take with food'},
            {'name': 'Albuterol', 'dosage': '90mcg', 'frequency': 'twice_daily', 'timings': ['08:00', '20:00'], 'instructions': '2 puffs as needed'},
            {'name': 'Montelukast', 'dosage': '10mg', 'frequency': 'once_daily', 'timings': ['21:00'], 'instructions': 'Take in the evening'},
            {'name': 'Glipizide', 'dosage': '5mg', 'frequency': 'twice_daily', 'timings': ['07:30', '17:30'], 'instructions': 'Take 30 min before meals'},
        ]

        # Adherence profiles per patient (controls how well they take medications)
        adherence_profiles = [
            {'taken': 0.80, 'late': 0.12, 'missed': 0.08, 'max_delay': 25},   # John - good
            {'taken': 0.60, 'late': 0.15, 'missed': 0.25, 'max_delay': 45},   # Mary - moderate
            {'taken': 0.90, 'late': 0.08, 'missed': 0.02, 'max_delay': 20},   # James - excellent
            {'taken': 0.70, 'late': 0.10, 'missed': 0.20, 'max_delay': 30},   # Sarah - decent
            {'taken': 0.35, 'late': 0.15, 'missed': 0.50, 'max_delay': 90},   # David - poor
        ]

        all_meds = {}
        for i, patient in enumerate(patients):
            num_meds = random.randint(2, 4)
            patient_meds = random.sample(medication_pool, k=num_meds)
            caretaker = patient.patient_profile.caretaker

            for med_data in patient_meds:
                med, created = Medication.objects.get_or_create(
                    name=med_data['name'],
                    patient=patient,
                    defaults={
                        'dosage': med_data['dosage'],
                        'frequency': med_data['frequency'],
                        'timings': med_data['timings'],
                        'instructions': med_data['instructions'],
                        'created_by': caretaker,
                        'is_active': True,
                    },
                )
                all_meds[(patient.id, med_data['name'])] = (med, med_data, adherence_profiles[i])
                status_str = 'created' if created else 'exists'
                self.stdout.write(
                    f'  [{status_str}] {patient.name}: {med.name} {med.dosage}'
                )

        # Generate 30 days of adherence logs
        self.stdout.write('\nGenerating adherence logs (30 days)...')
        total_logs = 0
        today = timezone.now().date()

        for (patient_id, med_name), (med, med_data, profile) in all_meds.items():
            patient = med.patient
            for day_offset in range(30, 0, -1):
                log_date = today - timedelta(days=day_offset)
                for timing_str in med_data['timings']:
                    hour, minute = map(int, timing_str.split(':'))
                    scheduled_dt = timezone.make_aware(
                        datetime.combine(log_date, time(hour, minute))
                    )

                    # Check if log already exists
                    if AdherenceLog.objects.filter(
                        medication=med, patient=patient, scheduled_time=scheduled_dt
                    ).exists():
                        continue

                    roll = random.random()
                    if roll < profile['taken']:
                        delay_min = random.randint(0, 5)
                        taken_dt = scheduled_dt + timedelta(minutes=delay_min)
                        log_status = 'taken'
                    elif roll < profile['taken'] + profile['late']:
                        delay_min = random.randint(15, profile['max_delay'])
                        taken_dt = scheduled_dt + timedelta(minutes=delay_min)
                        log_status = 'late'
                    else:
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

        self.stdout.write(f'  Generated {total_logs} adherence log entries.')

        # Create sample prescriptions
        self.stdout.write('\nCreating sample prescriptions...')
        sample_prescriptions = [
            {
                'patient': patients[0],
                'uploaded_by': caretakers[0],
                'extracted_data': {
                    'medications': [
                        {'name': 'Metformin', 'dosage': '500mg', 'frequency': 'twice_daily'},
                        {'name': 'Lisinopril', 'dosage': '10mg', 'frequency': 'once_daily'},
                    ],
                    'doctor_name': 'Dr. Robert Smith',
                    'date': '2026-01-15',
                },
            },
            {
                'patient': patients[1],
                'uploaded_by': caretakers[0],
                'extracted_data': {
                    'medications': [
                        {'name': 'Atorvastatin', 'dosage': '20mg', 'frequency': 'once_daily'},
                    ],
                    'doctor_name': 'Dr. Robert Smith',
                    'date': '2026-01-20',
                },
            },
            {
                'patient': patients[4],
                'uploaded_by': caretakers[1],
                'extracted_data': {
                    'medications': [
                        {'name': 'Metformin', 'dosage': '500mg', 'frequency': 'twice_daily'},
                        {'name': 'Aspirin', 'dosage': '81mg', 'frequency': 'once_daily'},
                        {'name': 'Metoprolol', 'dosage': '50mg', 'frequency': 'twice_daily'},
                    ],
                    'doctor_name': 'Dr. Priya Patel',
                    'date': '2026-02-01',
                },
            },
        ]

        for rx_data in sample_prescriptions:
            # Create without image (just extracted data for demo)
            Prescription.objects.create(
                image='',
                extracted_data=rx_data['extracted_data'],
                uploaded_by=rx_data['uploaded_by'],
                patient=rx_data['patient'],
            )
            self.stdout.write(
                f'  Created prescription for {rx_data["patient"].name}'
            )

        # Generate ML predictions
        self.stdout.write('\nTraining ML model and generating predictions...')
        trained = train_models()
        if trained:
            self.stdout.write('  ML model trained successfully.')
        else:
            self.stdout.write('  Using rule-based predictions (insufficient data for ML).')

        for patient in patients:
            predictions = generate_predictions_for_patient(patient)
            self.stdout.write(
                f'  Generated {len(predictions)} predictions for {patient.name}'
            )

        # Summary
        self.stdout.write(self.style.SUCCESS('\n--- Seed Complete ---'))
        self.stdout.write(f'Caretakers: {len(caretakers)}')
        self.stdout.write(f'Patients: {len(patients)}')
        self.stdout.write(f'Medications: {Medication.objects.count()}')
        self.stdout.write(f'Adherence Logs: {AdherenceLog.objects.count()}')
        self.stdout.write(f'Prescriptions: {Prescription.objects.count()}')
        self.stdout.write(f'Predictions: {Prediction.objects.count()}')
        self.stdout.write(f'\nAll demo users password: {DEMO_PASSWORD}')
        self.stdout.write('Caretaker logins:')
        for c in caretakers:
            self.stdout.write(f'  {c.email}')
        self.stdout.write('Patient logins:')
        for p in patients:
            self.stdout.write(f'  {p.email}')
