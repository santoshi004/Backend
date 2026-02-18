from django.contrib import admin

from .models import AdherenceLog


@admin.register(AdherenceLog)
class AdherenceLogAdmin(admin.ModelAdmin):
    list_display = ('medication', 'patient', 'scheduled_time', 'taken_time', 'status', 'created_at')
    list_filter = ('status', 'scheduled_time')
    search_fields = ('medication__name', 'patient__name', 'patient__email')
    raw_id_fields = ('medication', 'patient')
    date_hierarchy = 'scheduled_time'
