from django.contrib import admin

from .models import Prediction


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ('patient', 'medication', 'risk_level', 'predicted_delay_minutes', 'generated_at')
    list_filter = ('risk_level', 'generated_at')
    search_fields = ('patient__name', 'patient__email', 'medication__name')
    raw_id_fields = ('patient', 'medication')
