from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from medications.models import Medication, PatientProfile
from .models import AdherenceLog
from .serializers import (
    AdherenceLogCreateSerializer,
    AdherenceLogSerializer,
    AdherenceStatsSerializer,
    ScheduleEntrySerializer,
)


def _resolve_patient(request):
    """
    Resolve the target patient from the request.
    - If patient_id query param is provided and user is a caretaker, use that.
    - Otherwise use the authenticated user (must be a patient).
    Returns (patient_user, error_response).
    """
    user = request.user
    patient_id = request.query_params.get('patient_id')

    if patient_id:
        if user.role == 'caretaker':
            # Verify caretaker has access to this patient
            from accounts.models import User
            try:
                patient_user = User.objects.get(id=patient_id, role='patient')
            except User.DoesNotExist:
                return None, Response(
                    {'error': 'not_found', 'message': 'Patient not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if not PatientProfile.objects.filter(
                user=patient_user, caretaker=user
            ).exists():
                return None, Response(
                    {'error': 'forbidden', 'message': 'Not your patient.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            return patient_user, None
        else:
            return None, Response(
                {'error': 'forbidden', 'message': 'Only caretakers can query other patients.'},
                status=status.HTTP_403_FORBIDDEN,
            )
    else:
        if user.role == 'patient':
            return user, None
        return None, Response(
            {'error': 'bad_request', 'message': 'patient_id is required for caretakers.'},
            status=status.HTTP_400_BAD_REQUEST,
        )


class AdherenceLogView(APIView):
    """POST /api/adherence/log/ - Patient logs medication intake."""

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        serializer = AdherenceLogCreateSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        log = serializer.save()
        return Response(
            AdherenceLogSerializer(log).data,
            status=status.HTTP_201_CREATED,
        )


class AdherenceHistoryView(APIView):
    """
    GET /api/adherence/history/?patient_id=X&from=DATE&to=DATE
    Returns adherence history with summary counts.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        patient_user, error = _resolve_patient(request)
        if error:
            return error

        queryset = AdherenceLog.objects.filter(
            patient=patient_user
        ).select_related('medication')

        # Date range filtering
        from_date = request.query_params.get('from')
        to_date = request.query_params.get('to')

        if from_date:
            try:
                from_dt = datetime.strptime(from_date, '%Y-%m-%d')
                from_dt = timezone.make_aware(
                    datetime.combine(from_dt.date(), time.min)
                )
                queryset = queryset.filter(scheduled_time__gte=from_dt)
            except ValueError:
                return Response(
                    {'error': 'bad_request', 'message': 'Invalid from date format. Use YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if to_date:
            try:
                to_dt = datetime.strptime(to_date, '%Y-%m-%d')
                to_dt = timezone.make_aware(
                    datetime.combine(to_dt.date(), time.max)
                )
                queryset = queryset.filter(scheduled_time__lte=to_dt)
            except ValueError:
                return Response(
                    {'error': 'bad_request', 'message': 'Invalid to date format. Use YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        logs = queryset.order_by('-scheduled_time')

        # Summary counts
        counts = logs.aggregate(
            total=Count('id'),
            taken=Count('id', filter=Q(status='taken')),
            missed=Count('id', filter=Q(status='missed')),
            late=Count('id', filter=Q(status='late')),
        )

        serializer = AdherenceLogSerializer(logs, many=True)
        return Response({
            'logs': serializer.data,
            'summary': counts,
        })


class AdherenceStatsView(APIView):
    """
    GET /api/adherence/stats/?patient_id=X
    Returns adherence rate, streaks, totals.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        patient_user, error = _resolve_patient(request)
        if error:
            return error

        logs = AdherenceLog.objects.filter(
            patient=patient_user
        ).order_by('scheduled_time')

        total = logs.count()
        taken = logs.filter(status='taken').count()
        missed = logs.filter(status='missed').count()
        late = logs.filter(status='late').count()
        
        from .utils.rates import calculate_adherence_rate
        adherence_rate = calculate_adherence_rate(patient_user)

        # Calculate streaks (consecutive taken days)
        current_streak = 0
        longest_streak = 0
        temp_streak = 0

        # Get distinct dates with all-taken status
        dates_with_logs = {}
        for log in logs:
            date_key = log.scheduled_time.date()
            if date_key not in dates_with_logs:
                dates_with_logs[date_key] = True
            if log.status != 'taken':
                dates_with_logs[date_key] = False

        sorted_dates = sorted(dates_with_logs.keys())
        for i, d in enumerate(sorted_dates):
            if dates_with_logs[d]:
                temp_streak += 1
                longest_streak = max(longest_streak, temp_streak)
            else:
                temp_streak = 0

        # Current streak: count backwards from most recent date
        current_streak = 0
        for d in reversed(sorted_dates):
            if dates_with_logs[d]:
                current_streak += 1
            else:
                break

        stats = {
            'total_scheduled': total,
            'total_taken': taken,
            'total_missed': missed,
            'total_late': late,
            'adherence_rate': round(adherence_rate, 2),
            'current_streak': current_streak,
            'longest_streak': longest_streak,
        }

        serializer = AdherenceStatsSerializer(stats)
        return Response(serializer.data)


class TodayScheduleView(APIView):
    """
    GET /api/schedule/today/
    Returns today's medication schedule for the authenticated patient.
    Dynamically generates schedule entries from medication timings.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        patient_user, error = _resolve_patient(request)
        if error:
            return error

        today = timezone.now().date()
        medications = Medication.objects.filter(
            patient=patient_user, is_active=True
        )

        # Get existing logs for today
        today_start = timezone.make_aware(datetime.combine(today, time.min))
        today_end = timezone.make_aware(datetime.combine(today, time.max))
        existing_logs = AdherenceLog.objects.filter(
            patient=patient_user,
            scheduled_time__range=(today_start, today_end),
        ).values_list('medication_id', 'scheduled_time', 'status', 'taken_time')

        # Build a lookup: (medication_id, scheduled_time_str) -> status
        log_lookup = {}
        for med_id, sched_time, log_status, t_time in existing_logs:
            time_key = sched_time.strftime('%H:%M')
            log_lookup[(med_id, time_key)] = {
                'status': log_status,
                'taken_time': t_time.isoformat() if t_time else None
            }

        schedule = []
        for med in medications:
            for timing_str in med.timings:
                try:
                    hour, minute = map(int, timing_str.split(':'))
                    scheduled_dt = timezone.make_aware(
                        datetime.combine(today, time(hour, minute))
                    )
                except (ValueError, TypeError):
                    continue

                log_data = log_lookup.get((med.id, timing_str), {'status': 'pending', 'taken_time': None})
                schedule.append({
                    'medication': {
                        'id': med.id,
                        'name': med.name,
                        'dosage': med.dosage,
                    },
                    'scheduled_time': scheduled_dt.isoformat(),
                    'instructions': med.instructions,
                    'status': log_data['status'],
                    'taken_time': log_data['taken_time'],
                })

        # Sort by scheduled time
        schedule.sort(key=lambda x: x['scheduled_time'])

        return Response({
            'date': today.isoformat(),
            'medications': schedule
        })


class AdherenceRemindersView(APIView):
    """
    GET /api/adherence/reminders/
    Returns pending medication reminders that need absolute attention (voice + notify).
    """
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        patient_user, error = _resolve_patient(request)
        if error:
            return error

        now = timezone.now()
        today = now.date()
        
        # We look for medications due today that are NOT logged
        medications = Medication.objects.filter(
            patient=patient_user, is_active=True
        )
        
        # Get existing logs for today to exclude already taken
        today_start = timezone.make_aware(datetime.combine(today, time.min))
        today_end = timezone.make_aware(datetime.combine(today, time.max))
        logged_med_ids = AdherenceLog.objects.filter(
            patient=patient_user,
            scheduled_time__range=(today_start, today_end),
        ).values_list('medication_id', flat=True)

        reminders = []
        for med in medications:
            if med.id in logged_med_ids:
                continue

            for timing_str in med.timings:
                try:
                    hour, minute = map(int, timing_str.split(':'))
                    scheduled_dt = timezone.make_aware(
                        datetime.combine(today, time(hour, minute))
                    )
                    
                    # If it's within the window (due in last 30 mins)
                    # and hasn't been logged
                    diff = now - scheduled_dt
                    if timedelta(minutes=0) <= diff <= timedelta(minutes=60):
                        reminders.append({
                            "id": med.id,
                            "title": "Medication Reminder",
                            "message": f"Time to take {med.name} ({med.dosage})",
                            "speech_text": f"Reminder: It's time to take your dose of {med.name}."
                        })
                except (ValueError, TypeError):
                    continue

        return Response({"reminders": reminders})
