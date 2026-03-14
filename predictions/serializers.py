from rest_framework import serializers

from accounts.serializers import UserSerializer
from medications.serializers import MedicationSerializer
from .models import Prediction


class PredictionSerializer(serializers.ModelSerializer):
    """Serializer for reading Prediction data."""

    patient = UserSerializer(read_only=True)
    medication = MedicationSerializer(read_only=True)

    class Meta:
        model = Prediction
        fields = (
            'id', 'patient', 'medication', 'predicted_delay_minutes',
            'risk_level', 'message', 'generated_at',
        )
        read_only_fields = fields
