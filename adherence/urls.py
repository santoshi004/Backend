from django.urls import path

from . import views

app_name = 'adherence'

urlpatterns = [
    path('adherence/log/', views.AdherenceLogView.as_view(), name='adherence-log'),
    path('adherence/history/', views.AdherenceHistoryView.as_view(), name='adherence-history'),
    path('adherence/stats/', views.AdherenceStatsView.as_view(), name='adherence-stats'),
    path('adherence/reminders/', views.AdherenceRemindersView.as_view(), name='adherence-reminders'),
    path('schedule/today/', views.TodayScheduleView.as_view(), name='schedule-today'),
]
