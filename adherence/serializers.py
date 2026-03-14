from rest_framework import serializers

from medications.serializers import MedicationSerializer
from .models import AdherenceLog


class AdherenceLogSerializer(serializers.ModelSerializer):
    """Serializer for reading adherence logs."""

    medication = MedicationSerializer(read_only=True)

    class Meta:
        model = AdherenceLog
        fields = (
            'id', 'medication', 'patient', 'scheduled_time',
            'taken_time', 'status', 'created_at',
        )
        read_only_fields = ('id', 'created_at')


class AdherenceLogCreateSerializer(serializers.Serializer):
    """Serializer for logging medication intake."""

    medication_id = serializers.IntegerField()
    scheduled_time = serializers.DateTimeField()
    taken_time = serializers.DateTimeField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=['taken', 'missed', 'late'])

    def validate_medication_id(self, value):
        from medications.models import Medication
        user = self.context['request'].user
        try:
            med = Medication.objects.get(id=value, patient=user, is_active=True)
        except Medication.DoesNotExist:
            raise serializers.ValidationError(
                'Medication not found or does not belong to you.'
            )
        return value

    def create(self, validated_data):
        from medications.models import Medication
        user = self.context['request'].user
        medication = Medication.objects.get(id=validated_data['medication_id'])
        return AdherenceLog.objects.create(
            medication=medication,
            patient=user,
            scheduled_time=validated_data['scheduled_time'],
            taken_time=validated_data.get('taken_time'),
            status=validated_data['status'],
        )


class AdherenceStatsSerializer(serializers.Serializer):
    """Serializer for adherence statistics output."""

    total_scheduled = serializers.IntegerField()
    total_taken = serializers.IntegerField()
    total_missed = serializers.IntegerField()
    total_late = serializers.IntegerField()
    adherence_rate = serializers.FloatField()
    current_streak = serializers.IntegerField()
    longest_streak = serializers.IntegerField()
    best_streak = serializers.IntegerField(source='longest_streak')


class ScheduleEntrySerializer(serializers.Serializer):
    """Serializer for a single schedule entry."""

    medication_id = serializers.IntegerField()
    medication_name = serializers.CharField()
    dosage = serializers.CharField()
    scheduled_time = serializers.DateTimeField()
    instructions = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
