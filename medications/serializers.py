from rest_framework import serializers

from accounts.serializers import UserSerializer
from adherence.models import AdherenceLog
from .models import Medication, PatientProfile


class PatientProfileSerializer(serializers.ModelSerializer):
    """Serializer for PatientProfile."""

    user = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)
    caretaker = UserSerializer(read_only=True)
    adherence_rate = serializers.SerializerMethodField()

    class Meta:
        model = PatientProfile
        fields = (
            "id",
            "user",
            "user_id",
            "age",
            "medical_conditions",
            "caretaker",
            "created_at",
            "adherence_rate",
        )
        read_only_fields = ("id", "created_at")

    def get_adherence_rate(self, obj):
        logs = AdherenceLog.objects.filter(patient=obj.user)
        total = logs.count()
        if total == 0:
            return None
        taken = logs.filter(status="taken").count()
        late = logs.filter(status="late").count()
        return round((taken + late) / total * 100, 2)


class PatientProfileCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a PatientProfile (caretaker use)."""

    user_id = serializers.IntegerField()

    class Meta:
        model = PatientProfile
        fields = ("id", "user_id", "age", "medical_conditions", "created_at")
        read_only_fields = ("id", "created_at")

    def validate_user_id(self, value):
        from accounts.models import User

        try:
            user = User.objects.get(id=value, role="patient")
        except User.DoesNotExist:
            raise serializers.ValidationError("Patient user not found or user is not a patient.")
        if PatientProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError("Patient profile already exists for this user.")
        return value

    def create(self, validated_data):
        validated_data["caretaker"] = self.context["request"].user
        from accounts.models import User

        validated_data["user"] = User.objects.get(id=validated_data.pop("user_id"))
        return super().create(validated_data)


class MedicationSerializer(serializers.ModelSerializer):
    """Serializer for reading Medication data."""

    patient = UserSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Medication
        fields = (
            "id",
            "name",
            "dosage",
            "frequency",
            "timings",
            "instructions",
            "patient",
            "created_by",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "created_at", "created_by")


class MedicationCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating medications."""

    patient_id = serializers.IntegerField()

    class Meta:
        model = Medication
        fields = (
            "id",
            "name",
            "dosage",
            "frequency",
            "timings",
            "instructions",
            "patient_id",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "created_at")
        extra_kwargs = {
            'dosage': {'allow_null': True, 'required': False},
            'frequency': {'allow_null': True, 'required': False},
        }

    def validate_patient_id(self, value):
        from accounts.models import User

        try:
            User.objects.get(id=value, role="patient")
        except User.DoesNotExist:
            raise serializers.ValidationError("Patient user not found or user is not a patient.")
        return value

    def validate_timings(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Timings must be a list of time strings.")
        for t in value:
            if not isinstance(t, str):
                raise serializers.ValidationError("Each timing must be a string in HH:MM format.")
        return value

    def create(self, validated_data):
        from accounts.models import User
        try:
            validated_data["patient"] = User.objects.get(id=validated_data.pop("patient_id"))
            validated_data["created_by"] = self.context["request"].user
            return super().create(validated_data)
        except Exception as e:
            print(f"SERIALIZER CREATE ERROR: {e}")
            print(f"VALIDATED DATA: {validated_data}")
            raise e

    def update(self, instance, validated_data):
        if "patient_id" in validated_data:
            from accounts.models import User

            validated_data["patient"] = User.objects.get(id=validated_data.pop("patient_id"))
        return super().update(instance, validated_data)
