from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'medications'

router = DefaultRouter()
router.register(r'patients', views.PatientProfileViewSet, basename='patient-profile')
router.register(r'medications', views.MedicationViewSet, basename='medication')

urlpatterns = [
    path('', include(router.urls)),
]
