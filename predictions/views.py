from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from medications.models import PatientProfile
from .models import Prediction
from .serializers import PredictionSerializer
from .services.ml_service import generate_predictions_for_patient, train_models


class PredictionListView(APIView):
    """
    GET /api/predictions/{patient_id}/
    Get the latest predictions for a patient.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, patient_id, *args, **kwargs):
        user = request.user

        try:
            patient = User.objects.get(id=patient_id, role='patient')
        except User.DoesNotExist:
            return Response(
                {'error': 'not_found', 'message': 'Patient not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Permission check
        if user.role == 'patient' and user.id != patient_id:
            return Response(
                {'error': 'forbidden', 'message': 'You can only view your own predictions.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if user.role == 'caretaker':
            if not PatientProfile.objects.filter(
                user=patient, caretaker=user
            ).exists():
                return Response(
                    {'error': 'forbidden', 'message': 'Not your patient.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Get the latest prediction per medication
        predictions = Prediction.objects.filter(
            patient=patient
        ).select_related('patient', 'medication').order_by(
            'medication_id', '-generated_at'
        ).distinct('medication_id') if 'postgresql' in str(
            type(Prediction.objects.db)
        ) else Prediction.objects.filter(patient=patient).select_related(
            'patient', 'medication'
        )

        # For non-PostgreSQL, manually get latest per medication
        from django.db import connection
        if 'postgresql' in connection.vendor:
            predictions = Prediction.objects.filter(
                patient=patient
            ).select_related('patient', 'medication').order_by(
                'medication_id', '-generated_at'
            ).distinct('medication_id')
        else:
            # Fallback: get latest predictions (may include duplicates)
            seen_meds = set()
            latest = []
            for pred in Prediction.objects.filter(
                patient=patient
            ).select_related('patient', 'medication').order_by('-generated_at'):
                if pred.medication_id not in seen_meds:
                    seen_meds.add(pred.medication_id)
                    latest.append(pred)
            predictions = latest

        serializer = PredictionSerializer(predictions, many=True)
        
        # Calculate overall risk
        overall_risk = 'low'
        if any(p.risk_level == 'high' for p in (latest if connection.vendor != 'postgresql' else predictions)):
            overall_risk = 'high'
        elif any(p.risk_level == 'medium' for p in (latest if connection.vendor != 'postgresql' else predictions)):
            overall_risk = 'medium'

        return Response({
            'predictions': serializer.data,
            'overall_risk': overall_risk,
            'patient_id': patient.id
        })


class GeneratePredictionView(APIView):
    """
    POST /api/predictions/generate/
    Trigger ML model re-run for a patient.
    Body: {"patient_id": X}
    """

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        patient_id = request.data.get('patient_id')
        if not patient_id:
            return Response(
                {'error': 'bad_request', 'message': 'patient_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user

        try:
            patient = User.objects.get(id=patient_id, role='patient')
        except User.DoesNotExist:
            return Response(
                {'error': 'not_found', 'message': 'Patient not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Permission check
        if user.role == 'patient' and user.id != patient_id:
            return Response(
                {'error': 'forbidden', 'message': 'You can only generate predictions for yourself.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if user.role == 'caretaker':
            if not PatientProfile.objects.filter(
                user=patient, caretaker=user
            ).exists():
                return Response(
                    {'error': 'forbidden', 'message': 'Not your patient.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Try to train models first (will use existing data)
        train_models()

        # Generate predictions
        predictions = generate_predictions_for_patient(patient)
        serializer = PredictionSerializer(predictions, many=True)

        return Response(
            {
                'message': f'Generated {len(predictions)} predictions.',
                'predictions': serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )
