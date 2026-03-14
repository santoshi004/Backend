from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import IsCaretaker, IsOwnerOrCaretaker
from adherence.models import AdherenceLog
from .models import Medication, PatientProfile
from .serializers import (
    MedicationCreateUpdateSerializer,
    MedicationSerializer,
    PatientProfileCreateSerializer,
    PatientProfileSerializer,
)


class PatientProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for PatientProfile.

    - Caretakers can list their patients, create profiles, view/update details.
    - Patients can view their own profile.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def get_serializer_class(self):
        if self.action in ("create",):
            return PatientProfileCreateSerializer
        return PatientProfileSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == "caretaker":
            return PatientProfile.objects.filter(caretaker=user).select_related("user", "caretaker")
        # Patients see only their own profile
        return PatientProfile.objects.filter(user=user).select_related("user", "caretaker")

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated(), IsCaretaker()]
        return [permissions.IsAuthenticated()]

    def perform_destroy(self, instance):
        """Only caretakers can delete patient profiles."""
        if self.request.user.role != "caretaker":
            return Response(
                {"error": "forbidden", "message": "Only caretakers can delete profiles."},
                status=status.HTTP_403_FORBIDDEN,
            )
        instance.delete()

    def destroy(self, request, *args, **kwargs):
        if request.user.role != "caretaker":
            return Response(
                {"error": "forbidden", "message": "Only caretakers can delete profiles."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def detail_with_data(self, request, pk=None):
        """Get patient details with medications and adherence stats."""
        patient_profile = self.get_object()

        # Get medications
        medications = Medication.objects.filter(patient=patient_profile.user, is_active=True).select_related("created_by")

        # Get adherence stats
        logs = AdherenceLog.objects.filter(patient=patient_profile.user)
        total = logs.count()
        taken = logs.filter(status="taken").count()
        missed = logs.filter(status="missed").count()
        late = logs.filter(status="late").count()

        adherence_rate = round((taken + late) / total * 100, 2) if total > 0 else 0

        return Response(
            {
                "id": patient_profile.id,
                "user": {
                    "id": patient_profile.user.id,
                    "name": patient_profile.user.name,
                    "email": patient_profile.user.email,
                },
                "age": patient_profile.age,
                "medical_conditions": patient_profile.medical_conditions,
                "adherence_rate": adherence_rate,
                "adherence_stats": {
                    "total": total,
                    "taken": taken,
                    "missed": missed,
                    "late": late,
                },
                "medications": MedicationSerializer(medications, many=True).data,
            }
        )


class MedicationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Medication.

    - Caretakers can CRUD medications for their patients.
    - Patients can view their own medications (read-only).
    """

    permission_classes = (permissions.IsAuthenticated,)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return MedicationCreateUpdateSerializer
        return MedicationSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Medication.objects.select_related("patient", "created_by")

        if user.role == "caretaker":
            # Caretakers see medications for their patients
            patient_ids = PatientProfile.objects.filter(caretaker=user).values_list("user_id", flat=True)
            queryset = queryset.filter(patient_id__in=patient_ids)
        else:
            # Patients see only their own medications
            queryset = queryset.filter(patient=user)

        # Filter by active status (default: show only active)
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")
        else:
            queryset = queryset.filter(is_active=True)

        # Optional patient_id filter for caretakers
        patient_id = self.request.query_params.get("patient_id")
        if patient_id and user.role == "caretaker":
            queryset = queryset.filter(patient_id=patient_id)

        return queryset

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsCaretaker()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        try:
            serializer.save()
        except Exception as e:
            print(f"ERROR SAVING MEDICATION: {e}")
            raise e

    def perform_destroy(self, instance):
        """Soft delete - set is_active to False."""
        instance.is_active = False
        instance.save(update_fields=["is_active"])
