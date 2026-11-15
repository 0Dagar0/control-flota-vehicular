"""Rutas de la flota."""

from django.urls import path

from . import views

app_name = "flota"

urlpatterns = [
    path("", views.VehiculoListaView.as_view(), name="lista"),
    path("vehiculos/<str:placa>/", views.VehiculoDetalleView.as_view(), name="detalle"),
    path("documentos/", views.DocumentoListaView.as_view(), name="documentos"),
]
