from django.conf import settings
from django.db import models


class PatientProfile(models.Model):
    """Extended profile for patients, linking them to a caretaker."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='patient_profile',
    )
    age = models.PositiveIntegerField(null=True, blank=True)
    medical_conditions = models.TextField(blank=True, default='')
    caretaker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='patients',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Profile: {self.user.name}'


class Medication(models.Model):
    """Medication prescribed to a patient."""

    FREQUENCY_CHOICES = (
        ('once_daily', 'Once Daily'),
        ('twice_daily', 'Twice Daily'),
        ('thrice_daily', 'Thrice Daily'),
        ('custom', 'Custom'),
    )

    name = models.CharField(max_length=255)
    dosage = models.CharField(max_length=100, blank=True, null=True, default='')
    frequency = models.CharField(max_length=100, blank=True, null=True, default='')
    timings = models.JSONField(
        default=list,
        help_text='List of time strings, e.g. ["08:00", "20:00"]',
    )
    instructions = models.TextField(blank=True, default='')
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='medications',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_medications',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.dosage}) - {self.patient.name}'
