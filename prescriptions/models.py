from django.conf import settings
from django.db import models


class Prescription(models.Model):
    """Scanned prescription with OCR-extracted data."""

    image = models.ImageField(upload_to='prescriptions/%Y/%m/')
    extracted_data = models.JSONField(default=dict, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_prescriptions',
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='prescriptions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Prescription for {self.patient.name} ({self.created_at.date()})'
