"""
ML service for predicting medication adherence risk.

Uses scikit-learn RandomForest models to predict:
- Risk level (low/medium/high) via RandomForestClassifier
- Predicted delay in minutes via RandomForestRegressor

Features engineered from AdherenceLog data:
- avg_delay: average delay in minutes when taken late
- miss_rate: fraction of doses missed
- late_rate: fraction of doses taken late
- day_pattern_*: day-of-week adherence patterns (7 features)
- time_pattern_*: time-of-day adherence patterns (4 features: morning/afternoon/evening/night)
- consecutive_misses: max consecutive missed doses
- total_logs: total number of adherence log entries
"""

import logging
import os
import pickle
from collections import defaultdict

import numpy as np
from django.conf import settings
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(settings.BASE_DIR, 'ml_models')
CLASSIFIER_PATH = os.path.join(MODEL_DIR, 'risk_classifier.pkl')
REGRESSOR_PATH = os.path.join(MODEL_DIR, 'delay_regressor.pkl')


def _extract_features(adherence_logs):
    """
    Extract ML features from a list of AdherenceLog instances.

    Returns a feature dict with:
    - avg_delay, miss_rate, late_rate
    - day_pattern_0..6 (Mon=0 to Sun=6)
    - time_pattern_morning, afternoon, evening, night
    - consecutive_misses
    - total_logs
    """
    if not adherence_logs:
        return _empty_features()

    total = len(adherence_logs)
    delays = []
    missed = 0
    late = 0
    taken = 0
    day_taken = defaultdict(int)
    day_total = defaultdict(int)
    time_taken = defaultdict(int)
    time_total = defaultdict(int)
    max_consecutive_misses = 0
    current_consecutive = 0

    for log in adherence_logs:
        sched = log.scheduled_time
        day_total[sched.weekday()] += 1
        hour = sched.hour

        # Categorize time of day
        if 5 <= hour < 12:
            time_bucket = 'morning'
        elif 12 <= hour < 17:
            time_bucket = 'afternoon'
        elif 17 <= hour < 21:
            time_bucket = 'evening'
        else:
            time_bucket = 'night'
        time_total[time_bucket] += 1

        if log.status == 'taken':
            taken += 1
            day_taken[sched.weekday()] += 1
            time_taken[time_bucket] += 1
            current_consecutive = 0
            if log.taken_time and log.scheduled_time:
                delay = (log.taken_time - log.scheduled_time).total_seconds() / 60.0
                delays.append(max(0, delay))
        elif log.status == 'late':
            late += 1
            day_taken[sched.weekday()] += 1
            time_taken[time_bucket] += 1
            current_consecutive = 0
            if log.taken_time and log.scheduled_time:
                delay = (log.taken_time - log.scheduled_time).total_seconds() / 60.0
                delays.append(max(0, delay))
        elif log.status == 'missed':
            missed += 1
            current_consecutive += 1
            max_consecutive_misses = max(max_consecutive_misses, current_consecutive)

    # Calculate our new weighted adherence feature
    from adherence.utils.rates import calculate_adherence_rate
    # Create a temporary list of logs for the utility (which usually queries the DB)
    # But here we already have the logs, so we can mock a minimal patient or just 
    # use the raw math directly for efficiency.
    
    total_score = 0.0
    for log in adherence_logs:
        if log.status == 'taken':
            total_score += 1.0
        elif log.status == 'late':
            if log.taken_time and log.scheduled_time:
                delay_delta = log.taken_time - log.scheduled_time
                delay_hours = delay_delta.total_seconds() / 3600.0
                effective_late_hours = max(0, delay_hours - 1)
                total_score += max(0.4, 1.0 - (effective_late_hours / 10.0))
            else:
                total_score += 0.5
        # Status 'missed' is 0.0
        
    weighted_adherence = (total_score / total) * 100 if total > 0 else 0.0

    avg_delay = np.mean(delays) if delays else 0.0
    miss_rate = missed / total if total > 0 else 0.0
    late_rate = late / total if total > 0 else 0.0

    features = {
        'avg_delay': avg_delay,
        'miss_rate': miss_rate,
        'late_rate': late_rate,
        'weighted_adherence': weighted_adherence,
        'consecutive_misses': max_consecutive_misses,
        'total_logs': total,
    }

    # Day-of-week patterns (adherence rate per day)
    for d in range(7):
        if day_total[d] > 0:
            features[f'day_pattern_{d}'] = day_taken[d] / day_total[d]
        else:
            features[f'day_pattern_{d}'] = 1.0  # No data = assume good

    # Time-of-day patterns
    for tb in ['morning', 'afternoon', 'evening', 'night']:
        if time_total[tb] > 0:
            features[f'time_pattern_{tb}'] = time_taken[tb] / time_total[tb]
        else:
            features[f'time_pattern_{tb}'] = 1.0

    return features


def _empty_features():
    """Return default features when no data is available."""
    features = {
        'avg_delay': 0.0,
        'miss_rate': 0.0,
        'late_rate': 0.0,
        'consecutive_misses': 0,
        'total_logs': 0,
    }
    for d in range(7):
        features[f'day_pattern_{d}'] = 1.0
    for tb in ['morning', 'afternoon', 'evening', 'night']:
        features[f'time_pattern_{tb}'] = 1.0
    return features


def _features_to_array(features):
    """Convert feature dict to numpy array in consistent order."""
    feature_order = [
        'avg_delay', 'miss_rate', 'late_rate', 'weighted_adherence',
        'consecutive_misses', 'total_logs',
        'day_pattern_0', 'day_pattern_1', 'day_pattern_2', 'day_pattern_3',
        'day_pattern_4', 'day_pattern_5', 'day_pattern_6',
        'time_pattern_morning', 'time_pattern_afternoon',
        'time_pattern_evening', 'time_pattern_night',
    ]
    return np.array([features[f] for f in feature_order]).reshape(1, -1)


def train_models():
    """
    Train the ML models on existing adherence data.
    Creates both a classifier (risk level) and regressor (delay prediction).
    """
    from adherence.models import AdherenceLog
    from accounts.models import User
    from medications.models import Medication

    logger.info('Training ML models...')

    patients = User.objects.filter(role='patient')

    X_data = []
    y_risk = []
    y_delay = []

    for patient in patients:
        medications = Medication.objects.filter(patient=patient, is_active=True)
        for med in medications:
            logs = list(
                AdherenceLog.objects.filter(
                    patient=patient, medication=med
                ).order_by('scheduled_time')
            )
            if len(logs) < 5:
                continue

            features = _extract_features(logs)
            X_data.append(_features_to_array(features).flatten())

            # Determine ground truth risk level using Weighted Adherence
            score = features['weighted_adherence']
            if score <= 50.0 or features['consecutive_misses'] >= 5:
                y_risk.append('high')
            elif score <= 80.0:
                y_risk.append('medium')
            else:
                y_risk.append('low')

            y_delay.append(features['avg_delay'])

    if len(X_data) < 3:
        logger.warning(
            'Not enough data to train models (need at least 3 patient-medication pairs). '
            'Using rule-based fallback.'
        )
        return False

    X = np.array(X_data)
    y_risk_arr = np.array(y_risk)
    y_delay_arr = np.array(y_delay)

    # Train classifier
    classifier = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
    )
    classifier.fit(X, y_risk_arr)

    # Train regressor
    regressor = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        random_state=42,
    )
    regressor.fit(X, y_delay_arr)

    # Save models
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(CLASSIFIER_PATH, 'wb') as f:
        pickle.dump(classifier, f)
    with open(REGRESSOR_PATH, 'wb') as f:
        pickle.dump(regressor, f)

    logger.info(f'Models trained on {len(X_data)} samples and saved.')
    return True


def _load_models():
    """Load trained models from disk. Returns (classifier, regressor) or (None, None)."""
    if not os.path.exists(CLASSIFIER_PATH) or not os.path.exists(REGRESSOR_PATH):
        return None, None
    try:
        with open(CLASSIFIER_PATH, 'rb') as f:
            classifier = pickle.load(f)
        with open(REGRESSOR_PATH, 'rb') as f:
            regressor = pickle.load(f)
        return classifier, regressor
    except Exception as e:
        logger.error(f'Failed to load models: {e}')
        return None, None


def _rule_based_prediction(features):
    """
    Fallback rule-based prediction when ML models are not available.
    """
    score = features.get('weighted_adherence', 100.0)
    avg_delay = features['avg_delay']

    if score <= 50.0 or features['consecutive_misses'] >= 5:
        risk_level = 'high'
    elif score <= 80.0 or avg_delay >= 30:
        risk_level = 'medium'
    else:
        risk_level = 'low'

    predicted_delay = int(avg_delay)

    messages = {
        'low': 'Good adherence pattern. Keep it up!',
        'medium': 'Some doses are being missed or taken late. Consider setting reminders.',
        'high': 'Significant adherence issues detected. Please consult with your caretaker.',
    }

    return {
        'risk_level': risk_level,
        'predicted_delay_minutes': predicted_delay,
        'message': messages[risk_level],
    }


def predict_for_patient_medication(patient, medication):
    """
    Generate prediction for a specific patient-medication pair.

    Args:
        patient: User instance (patient)
        medication: Medication instance

    Returns:
        dict with risk_level, predicted_delay_minutes, message
    """
    from adherence.models import AdherenceLog

    logs = list(
        AdherenceLog.objects.filter(
            patient=patient, medication=medication
        ).order_by('scheduled_time')
    )

    features = _extract_features(logs)

    # Try ML model first
    classifier, regressor = _load_models()
    if classifier is not None and regressor is not None:
        X = _features_to_array(features)
        risk_level = classifier.predict(X)[0]
        predicted_delay = max(0, int(regressor.predict(X)[0]))

        messages = {
            'low': 'ML analysis shows good adherence pattern. Keep it up!',
            'medium': 'ML analysis indicates some adherence concerns. Consider setting reminders.',
            'high': 'ML analysis detected significant adherence risk. Please review with your caretaker.',
        }

        return {
            'risk_level': risk_level,
            'predicted_delay_minutes': predicted_delay,
            'message': messages[risk_level],
        }

    # Fallback to rule-based
    return _rule_based_prediction(features)


def generate_predictions_for_patient(patient):
    """
    Generate predictions for all active medications of a patient.
    Saves results to the Prediction model.

    Args:
        patient: User instance (patient)

    Returns:
        list of Prediction instances created
    """
    from medications.models import Medication
    from predictions.models import Prediction

    medications = Medication.objects.filter(patient=patient, is_active=True)
    predictions = []

    for med in medications:
        result = predict_for_patient_medication(patient, med)

        prediction = Prediction.objects.create(
            patient=patient,
            medication=med,
            predicted_delay_minutes=result['predicted_delay_minutes'],
            risk_level=result['risk_level'],
            message=result['message'],
        )
        predictions.append(prediction)

    return predictions
