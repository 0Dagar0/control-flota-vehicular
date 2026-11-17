"""Pruebas de las páginas de error 403, 404 y 500 (encargo 03)."""

from datetime import timedelta

import pytest
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.flota.models import Conductor
from apps.usuarios.models import Usuario

CLAVE = "ClaveSegura2026"


@pytest.fixture
def conductor(db):
    usuario = Usuario.objects.create_user(
        documento="10203040",
        email="conductor@ejemplo.com",
        password=CLAVE,
        first_name="Carlos",
        last_name="Pérez",
        rol=Usuario.Rol.CONDUCTOR,
    )
    return Conductor.objects.create(
        usuario=usuario,
        licencia_vencimiento=timezone.localdate() + timedelta(days=365),
    )


@override_settings(DEBUG=False)
def test_403_muestra_la_plantilla_del_contrato(client, conductor):
    """Un conductor que entra por URL a la flota ve la tarjeta 403."""
    client.force_login(conductor.usuario)
    respuesta = client.get(reverse("flota:lista"))
    contenido = respuesta.content.decode()
    assert respuesta.status_code == 403
    assert "No tienes permiso" in contenido
    assert "403" in contenido
    # El marcador neutro sustituye al logo real.
    assert "MF" in contenido


@override_settings(DEBUG=False)
def test_404_muestra_la_plantilla_del_contrato(client):
    respuesta = client.get("/esta-ruta-no-existe/")
    contenido = respuesta.content.decode()
    assert respuesta.status_code == 404
    assert "La página no existe" in contenido
    assert "404" in contenido
    assert "MF" in contenido


@override_settings(DEBUG=False, ROOT_URLCONF="tests.urls_error")
def test_500_muestra_la_plantilla_del_contrato():
    """La vista de error no filtra el mensaje de la excepción."""
    cliente = Client(raise_request_exception=False)
    respuesta = cliente.get("/boom/")
    contenido = respuesta.content.decode()
    assert respuesta.status_code == 500
    assert "Error del servidor" in contenido
    assert "Fallo provocado por la prueba" not in contenido
    assert "MF" in contenido
