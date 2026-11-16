"""Rutas del servicio del conductor (contrato §5.1)."""

from django.urls import path

from . import views

app_name = "servicio"

urlpatterns = [
    path("iniciar/", views.ServicioIniciarView.as_view(), name="iniciar"),
    path("<int:pk>/cerrar/", views.ServicioCerrarView.as_view(), name="cerrar"),
]
