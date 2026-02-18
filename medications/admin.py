from django.contrib import admin

from .models import Medication, PatientProfile


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'age', 'caretaker', 'created_at')
    list_filter = ('caretaker',)
    search_fields = ('user__name', 'user__email', 'medical_conditions')
    raw_id_fields = ('user', 'caretaker')


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'dosage', 'frequency', 'patient', 'is_active', 'created_at')
    list_filter = ('frequency', 'is_active')
    search_fields = ('name', 'patient__name', 'patient__email')
    raw_id_fields = ('patient', 'created_by')
