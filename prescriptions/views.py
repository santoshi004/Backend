from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from medications.models import PatientProfile
from .models import Prescription
from .serializers import PrescriptionScanSerializer, PrescriptionSerializer
from .services.ocr_service import extract_prescription_data


class PrescriptionScanView(APIView):
    """
    POST /api/prescriptions/scan/
    Upload a prescription image, run OCR, save and return extracted data.
    Both caretakers and patients can scan.
    """

    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        serializer = PrescriptionScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        patient_id = serializer.validated_data['patient_id']
        image = serializer.validated_data['image']
        patient_user = User.objects.get(id=patient_id)

        # Permission check: patient can only scan for self,
        # caretaker can scan for their patients
        user = request.user
        if user.role == 'patient' and user.id != patient_id:
            return Response(
                {'error': 'forbidden', 'message': 'Patients can only scan for themselves.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if user.role == 'caretaker':
            if not PatientProfile.objects.filter(
                user=patient_user, caretaker=user
            ).exists():
                return Response(
                    {'error': 'forbidden', 'message': 'Not your patient.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Run OCR
        extracted_data = extract_prescription_data(image)

        # Print for feedback (as requested)
        print("\n" + "="*50)
        print(f"PRESCRIPTION SCANNED FOR: {patient_user.name} ({patient_user.email})")
        print(f"DOCTOR: {extracted_data.get('doctor_name', 'Unknown')}")
        print(f"DATE: {extracted_data.get('date', 'Unknown')}")
        print("MEDICATIONS EXTRACTED:")
        for med in extracted_data.get('medications', []):
            print(f" - {med.get('name')}: {med.get('dosage')} ({med.get('frequency')})")
        print("="*50 + "\n")

        # Save prescription
        prescription = Prescription.objects.create(
            image=image,
            extracted_data=extracted_data,
            uploaded_by=user,
            patient=patient_user,
        )

        return Response(
            PrescriptionSerializer(prescription).data,
            status=status.HTTP_201_CREATED,
        )


class PrescriptionListView(generics.ListAPIView):
    """
    GET /api/prescriptions/?patient_id=X
    List prescriptions for a patient.
    """

    serializer_class = PrescriptionSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        patient_id = self.request.query_params.get('patient_id')

        queryset = Prescription.objects.select_related('uploaded_by', 'patient')

        if user.role == 'caretaker':
            # Caretakers see prescriptions for their patients
            patient_ids = PatientProfile.objects.filter(
                caretaker=user
            ).values_list('user_id', flat=True)
            queryset = queryset.filter(patient_id__in=patient_ids)

            if patient_id:
                queryset = queryset.filter(patient_id=patient_id)
        else:
            # Patients see only their own prescriptions
            queryset = queryset.filter(patient=user)

        return queryset


class PrescriptionDetailView(generics.RetrieveDestroyAPIView):
    """
    GET/DELETE /api/prescriptions/<pk>/
    Retrieve or delete a prescription.
    """

    serializer_class = PrescriptionSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        queryset = Prescription.objects.select_related('uploaded_by', 'patient')

        if user.role == 'caretaker':
            patient_ids = PatientProfile.objects.filter(
                caretaker=user
            ).values_list('user_id', flat=True)
            queryset = queryset.filter(patient_id__in=patient_ids)
        else:
            queryset = queryset.filter(patient=user)

        return queryset
