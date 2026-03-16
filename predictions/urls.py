from django.urls import path

from . import views

app_name = 'predictions'

urlpatterns = [
    path(
        'predictions/generate/',
        views.GeneratePredictionView.as_view(),
        name='prediction-generate',
    ),
    path(
        'predictions/<int:patient_id>/',
        views.PredictionListView.as_view(),
        name='prediction-list',
    ),
    path(
        'predictions/playground/',
        views.PredictionPlaygroundView.as_view(),
        name='prediction-playground',
    ),
]
