from django.db.models import Q
from ..models import AdherenceLog

def calculate_adherence_rate(patient_user):
    """
    Calculates a time-weighted adherence rate.
    Weighting:
    - Taken (on time): 1.0
    - Late: max(0.4, 1.0 - (hours_late / 10))
    - Missed: 0.0
    """
    logs = AdherenceLog.objects.filter(patient=patient_user)
    total_count = logs.count()
    
    if total_count == 0:
        return 0.0
        
    total_score = 0.0
    
    for log in logs:
        if log.status == 'taken':
            total_score += 1.0
        elif log.status == 'missed':
            total_score += 0.0
        elif log.status == 'late':
            if log.taken_time and log.scheduled_time:
                delay_delta = log.taken_time - log.scheduled_time
                delay_hours = delay_delta.total_seconds() / 3600.0
                # Subtract 1 hour from delay because 0-1h is 'taken' (full credit)
                effective_late_hours = max(0, delay_hours - 1)
                score = max(0.4, 1.0 - (effective_late_hours / 10.0))
                total_score += score
            else:
                # Fallback if taken_time is missing for some reason
                total_score += 0.5
                
    return round((total_score / total_count) * 100, 2)
