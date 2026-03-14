from django.urls import path

from . import views

app_name = 'prescriptions'

urlpatterns = [
    path('prescriptions/scan/', views.PrescriptionScanView.as_view(), name='prescription-scan'),
    path('prescriptions/', views.PrescriptionListView.as_view(), name='prescription-list'),
    path('prescriptions/<int:pk>/', views.PrescriptionDetailView.as_view(), name='prescription-detail'),
]
