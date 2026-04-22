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

    medication = serializers.IntegerField(required=False)
    medication_id = serializers.IntegerField(required=False)
    scheduled_time = serializers.DateTimeField(required=False, allow_null=True)
    taken_time = serializers.DateTimeField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=['taken', 'missed', 'late'])

    def validate(self, data):
        # Handle both medication and medication_id
        med_id = data.get('medication') or data.get('medication_id')
        if not med_id:
            raise serializers.ValidationError("Medication ID is required.")
        
        from medications.models import Medication
        user = self.context['request'].user
        try:
            med = Medication.objects.get(id=med_id, patient=user, is_active=True)
            data['medication_obj'] = med
        except Medication.DoesNotExist:
            raise serializers.ValidationError(
                'Medication not found or does not belong to you.'
            )
        return data

    def create(self, validated_data):
        from django.utils import timezone
        
        user = self.context['request'].user
        medication = validated_data['medication_obj']
        
        # Use provided scheduled_time or default to now
        scheduled_time = validated_data.get('scheduled_time') or timezone.now()
        
        return AdherenceLog.objects.create(
            medication=medication,
            patient=user,
            scheduled_time=scheduled_time,
            taken_time=validated_data.get('taken_time') or timezone.now(),
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
