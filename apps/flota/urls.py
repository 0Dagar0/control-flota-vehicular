"""Rutas de vehículos de la flota (contrato §5.2)."""

from django.urls import path

from . import views

app_name = "flota"

urlpatterns = [
    path("", views.VehiculoListaView.as_view(), name="lista"),
    path("<str:placa>/fotos/", views.VehiculoFotosView.as_view(), name="fotos"),
    path("<str:placa>/", views.VehiculoDetalleView.as_view(), name="detalle"),
]
