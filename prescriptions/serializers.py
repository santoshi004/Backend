from rest_framework import serializers

from accounts.serializers import UserSerializer
from .models import Prescription


class PrescriptionSerializer(serializers.ModelSerializer):
    """Serializer for reading Prescription data."""

    uploaded_by = UserSerializer(read_only=True)
    patient = UserSerializer(read_only=True)

    class Meta:
        model = Prescription
        fields = (
            'id', 'image', 'extracted_data', 'uploaded_by',
            'patient', 'created_at',
        )
        read_only_fields = ('id', 'extracted_data', 'uploaded_by', 'created_at')


class PrescriptionScanSerializer(serializers.Serializer):
    """Serializer for scanning/uploading a prescription."""

    image = serializers.ImageField()
    patient_id = serializers.IntegerField()

    def validate_patient_id(self, value):
        from accounts.models import User
        try:
            User.objects.get(id=value, role='patient')
        except User.DoesNotExist:
            raise serializers.ValidationError(
                'Patient user not found or user is not a patient.'
            )
        return value
