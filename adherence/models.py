from django.conf import settings
from django.db import models

from medications.models import Medication


class AdherenceLog(models.Model):
    """Log of medication adherence for a patient."""

    STATUS_CHOICES = (
        ('taken', 'Taken'),
        ('missed', 'Missed'),
        ('late', 'Late'),
    )

    medication = models.ForeignKey(
        Medication,
        on_delete=models.CASCADE,
        related_name='adherence_logs',
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='adherence_logs',
    )
    scheduled_time = models.DateTimeField()
    taken_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scheduled_time']
        indexes = [
            models.Index(fields=['patient', 'scheduled_time']),
            models.Index(fields=['medication', 'scheduled_time']),
        ]

    def __str__(self):
        return (
            f'{self.medication.name} - {self.patient.name} - '
            f'{self.scheduled_time} - {self.status}'
        )
