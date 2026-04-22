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
    now = timezone.localtime(timezone.now())
    current_time = now.time()
    
    print(f"--- TRIGGER CHECK AT {now.strftime('%H:%M:%S')} ---")
    
    meds = Medication.objects.filter(is_active=True)
    results = []
    
    for med in meds:
        if not med.timings:
            continue
            
        for timing_str in med.timings:
            try:
                hour, minute = map(int, timing_str.split(':'))
                
                # Construct a precise localized datetime for the scheduled dose
                scheduled_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # Check for match (within 2 minutes)
                time_match = (hour == current_time.hour and abs(minute - current_time.minute) < 2)
                
                if time_match:
                    print(f"[MATCH] Checking {med.patient.email}'s {med.name} (Scheduled: {timing_str})")
                    
                    # Check if logged for THIS SPECIFIC TIME today
                    start_window = scheduled_dt
                    end_window = scheduled_dt + timezone.timedelta(minutes=1)
                    
                    logged = AdherenceLog.objects.filter(
                        medication=med,
                        patient=med.patient,
                        scheduled_time__range=(start_window, end_window)
                    ).exists()
                    
                    # AGGRESSIVE MODE: Send push even if already logged (allows desktop/mobile sync)
                    print(f"  -> Triggering notification for {med.name}...")
                    res = send_medication_reminder(med.patient, med, "due")
                    results.append(res)
                    print(f"  -> {res}")

                    if logged:
                        print(f"  Note: Already logged, but push sent to ensure dual-device delivery.")
                # else:
                #    # Hidden to avoid clutter, but helpful for deep debugging:
                #    print(f"[SKIP] {med.name} at {timing_str} doesn't match {current_time.strftime('%H:%M')}")
                    
            except Exception as e:
                print(f"[ERROR] Logic failure for {med.name}: {str(e)}")
                
    if not results:
        print("--- NO MEDICATIONS DUE AT THIS TIME ---")
        
    return results
                
    return results
