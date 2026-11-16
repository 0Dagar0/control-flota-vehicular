"""Rutas de documentos (contrato §5.2: ``/documentos/``)."""

from django.urls import path

from . import views

app_name = "documentos"

urlpatterns = [
    path("", views.DocumentoListaView.as_view(), name="lista"),
]
