from django.contrib import admin

from .models import Prescription


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ('patient', 'uploaded_by', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('patient__name', 'patient__email', 'uploaded_by__name')
    raw_id_fields = ('patient', 'uploaded_by')
