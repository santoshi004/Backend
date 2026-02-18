from rest_framework.permissions import BasePermission


class IsCaretaker(BasePermission):
    """Allow access only to users with caretaker role."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'caretaker'
        )


class IsPatient(BasePermission):
    """Allow access only to users with patient role."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'patient'
        )


class IsOwnerOrCaretaker(BasePermission):
    """
    Allow access if the user is the owner of the resource
    or if the user is a caretaker linked to the patient.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superusers always have access
        if request.user.is_superuser:
            return True

        # Check if user is the owner (the patient themselves)
        patient_user = getattr(obj, 'patient', None) or getattr(obj, 'user', None)
        if patient_user == request.user:
            return True

        # Check if user is a caretaker for this patient
        if request.user.role == 'caretaker':
            # Check via PatientProfile if it exists
            from medications.models import PatientProfile
            return PatientProfile.objects.filter(
                user=patient_user,
                caretaker=request.user,
            ).exists()

        return False
