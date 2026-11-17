"""Pruebas del centro de alertas con datos reales (integración del encargo 03)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.flota.models import Conductor, Documento, Vehiculo
from apps.usuarios.models import Usuario

CLAVE = "ClaveSegura2026"


@pytest.fixture
def admin(db):
    return Usuario.objects.create_user(
        documento="900100100",
        email="admin@ejemplo.com",
        password=CLAVE,
        first_name="Ana",
        last_name="Rojas",
        rol=Usuario.Rol.ADMIN,
    )


@pytest.fixture
def vehiculo(db):
    return Vehiculo.objects.create(
        placa="ABC123",
        marca="FOTON",
        referencia="BJ1044",
        modelo=2025,
        km_actual=1000,
    )


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


def test_alerta_de_documento_vencido_y_licencia_sin_duplicar(
    client, admin, vehiculo, conductor
):
    ayer = timezone.localdate() - timedelta(days=1)
    Documento.objects.create(
        tipo=Documento.Tipo.SOAT,
        vehiculo=vehiculo,
        vencimiento=ayer,
    )
    # La licencia vencida se cuenta desde el conductor; el documento no debe repetirla.
    Documento.objects.create(
        tipo=Documento.Tipo.LICENCIA,
        conductor=conductor,
        vencimiento=ayer,
    )
    conductor.licencia_vencimiento = ayer
    conductor.save()

    client.force_login(admin)
    contenido = client.get(reverse("alertas")).content.decode()

    assert "SOAT vencido" in contenido
    assert "ABC123" in contenido
    assert ayer.strftime("%d/%m/%Y") in contenido
    assert contenido.count("Licencia vencida") == 1
    assert "Crítico" in contenido


def test_alertas_proximas_e_informativas(client, admin, vehiculo, conductor):
    Documento.objects.create(
        tipo=Documento.Tipo.TECNOMECANICA,
        vehiculo=vehiculo,
        vencimiento=timezone.localdate() + timedelta(days=3),
    )
    client.force_login(admin)
    contenido = client.get(reverse("alertas")).content.decode()

    assert "por vencer en 3 días" in contenido
    assert "Próximo" in contenido
    assert "Conductor activo sin vehículo asignado" in contenido
    assert "Vehículo sin fotos registradas" in contenido
    assert "Informativo" in contenido


def test_centro_vacio_cuando_no_hay_hechos_pendientes(client, admin):
    client.force_login(admin)
    respuesta = client.get(reverse("alertas"))
    assert respuesta.status_code == 200
    assert "Nada pendiente hoy" in respuesta.content.decode()


def test_el_conductor_no_entra_al_centro_de_alertas(client, conductor):
    client.force_login(conductor.usuario)
    assert client.get(reverse("alertas")).status_code == 403
