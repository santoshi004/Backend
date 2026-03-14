from django.conf import settings
from django.db import models

from medications.models import Medication


class Prediction(models.Model):
    """ML prediction for a patient's medication adherence."""

    RISK_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    )

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='predictions',
    )
    medication = models.ForeignKey(
        Medication,
        on_delete=models.CASCADE,
        related_name='predictions',
    )
    predicted_delay_minutes = models.IntegerField(default=0)
    risk_level = models.CharField(max_length=10, choices=RISK_CHOICES)
    message = models.TextField(blank=True, default='')
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return (
            f'{self.patient.name} - {self.medication.name}: '
            f'{self.risk_level} risk ({self.predicted_delay_minutes}min delay)'
        )
