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

class PredictionPlaygroundView(APIView):
    """
    POST /api/predictions/playground/
    Accepts raw features and returns a prediction for demo purposes.
    """
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        avg_delay = float(request.data.get('avg_delay', 0))
        miss_rate = float(request.data.get('miss_rate', 0))
        consecutive_misses = int(request.data.get('consecutive_misses', 0))
        
        # Calculate a simulated weighted adherence
        # Simulating 10 logs for the math
        total = 10
        missed_count = round(miss_rate * total)
        taken_count = total - missed_count
        
        # We assume 'taken' includes some 'late' penalty based on avg_delay
        # This is a simplification for the playground
        score = 0.0
        for _ in range(taken_count):
            if avg_delay <= 60: # taken within 1h
                score += 1.0
            else:
                delay_hours = avg_delay / 60.0
                effective_late_hours = max(0, delay_hours - 1)
                score += max(0.4, 1.0 - (effective_late_hours / 10.0))
        
        simulated_weighted = (score / total) * 100
        
        features = {
            'avg_delay': avg_delay,
            'miss_rate': miss_rate,
            'late_rate': 0.0, # Simple playground
            'weighted_adherence': simulated_weighted,
            'consecutive_misses': consecutive_misses,
            'total_logs': total,
        }
        # Fill patterns with 1.0
        for d in range(7): features[f'day_pattern_{d}'] = 1.0
        for tb in ['morning', 'afternoon', 'evening', 'night']: features[f'time_pattern_{tb}'] = 1.0
        
        from .services.ml_service import predict_for_patient_medication, _load_models, _features_to_array, _rule_based_prediction
        
        classifier, regressor = _load_models()
        # For the demo lab, we want to show the "Logic" even if ML is shy.
        # We'll use a Hybrid approach.
        
        # 1. Start with Rule-Based (Always works and is sensitive)
        res = _rule_based_prediction(features)
        risk_level = res['risk_level']
        pred_delay = res['predicted_delay_minutes']
        method = "Clinical Engine"

        # 2. Try to augment with ML if available
        if classifier and regressor:
            try:
                X = _features_to_array(features)
                ml_risk = classifier.predict(X)[0]
                # If ML is MORE concerned than rules, trust ML. 
                # Otherwise, keep rules as safety net for small datasets.
                if (ml_risk == 'high' and risk_level != 'high') or (ml_risk == 'medium' and risk_level == 'low'):
                    risk_level = ml_risk
                    method = "ML Random Forest"
                pred_delay = int(regressor.predict(X)[0])
            except:
                pass

        return Response({
            'risk_level': risk_level,
            'predicted_delay_minutes': pred_delay,
            'weighted_adherence': round(simulated_weighted, 2),
            'method_used': method,
            'explanation': f"Risk is {risk_level} because weighted adherence is {simulated_weighted:.1f}% and consecutive misses is {consecutive_misses}."
        })
