from webpush import send_group_notification
from medications.models import Medication
from adherence.models import AdherenceLog
from django.utils import timezone
from datetime import datetime, time

def send_medication_reminder(user, medication, reminder_type="due"):
    """
    Sends a WebPush notification with speech_text for audible alerts.
    """
    if reminder_type == "due":
        speech_text = f"It's time for your medication: {medication.name}. Please take {medication.dosage}."
        title = "Medication Due"
    else:
        speech_text = f"Warning: You have missed your dose of {medication.name}."
        title = "Missing Medication Alert"

    payload = {
        "head": title,
        "body": speech_text,
        "icon": "/logo.png",
        "url": "/patient/medications",
        "speech_text": speech_text  # This will be picked up by the Service Worker/Frontend
    }

    # Send to the user's group (django-webpush uses groups for targeted delivery)
    # The frontend will subscribe to a group named after the username or user ID
    group_name = f"user_{user.id}"
    
    try:
        send_group_notification(group_name=group_name, payload=payload, ttl=3600)
        return f"Push Reminder sent to {user.email} for {medication.name}"
    except Exception as e:
        # This usually means the user has not registered any device for WebPush yet
        if "Group matching query does not exist" in str(e):
            return f"Skipped: {user.email} has no registered push devices for {medication.name}"
        raise e

def check_and_trigger_reminders():
    """
    Logic to identify who needs a reminder NOW.
    """
    # Use localized time for comparison with medication timings
    now = timezone.localtime(timezone.now())
    current_time = now.time()
    
    # Simple logic: check medications due within the last 5 minutes that aren't logged
    # This is a simplified version for demonstration
    # In a real system, we'd use a more robust scheduling check
    meds = Medication.objects.all()
    results = []
    
    for med in meds:
        # Assuming timings is a list of strings like ["08:00", "20:00"]
        for timing_str in med.timings:
            try:
                hour, minute = map(int, timing_str.split(':'))
                # If current time is past the timing but within an hour
                # and no log exists for today
                # (This is very basic logic for the prototype)
                if hour == current_time.hour and abs(minute - current_time.minute) < 2:
                    # Check if logged today
                    logged = AdherenceLog.objects.filter(
                        medication=med,
                        patient=med.patient,
                        scheduled_time__date=now.date()
                    ).exists()
                    
                    if not logged:
                        res = send_medication_reminder(med.patient, med, "due")
                        results.append(res)
            except Exception:
                pass
                
    return results
