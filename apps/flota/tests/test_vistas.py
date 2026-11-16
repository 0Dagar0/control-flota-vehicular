"""Pruebas de las vistas de la flota y del acceso por rol (v0.3)."""

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
        licencia_categoria=Conductor.CategoriaLicencia.C2,
        licencia_vencimiento=timezone.localdate() + timedelta(days=365),
    )


@pytest.fixture
def vehiculo(db):
    return Vehiculo.objects.create(
        placa="ABC123",
        marca="FOTON",
        referencia="BJ1044VAJB3-1A",
        modelo=2025,
        km_actual=1000,
    )


@pytest.fixture
def documento_sin_soporte(db, vehiculo):
    return Documento.objects.create(
        tipo=Documento.Tipo.SOAT,
        vehiculo=vehiculo,
        entidad="Aseguradora de prueba",
        vencimiento=timezone.localdate() + timedelta(days=200),
    )


def test_anonimo_va_al_login(client):
    """Sin sesión iniciada, la flota redirige al login y recuerda a dónde iba."""
    respuesta = client.get(reverse("flota:lista"))
    assert respuesta.status_code == 302
    assert reverse("login") in respuesta["Location"]
    assert reverse("flota:lista") in respuesta["Location"]


def test_portada_sin_sesion_va_al_login(client):
    respuesta = client.get(reverse("inicio"))
    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("login")


def test_portada_del_admin_va_a_la_flota(client, admin):
    client.force_login(admin)
    respuesta = client.get(reverse("inicio"))
    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("flota:lista")


def test_portada_del_conductor_va_a_mi_servicio(client, conductor):
    """v0.5: el conductor ya tiene pantalla propia."""
    client.force_login(conductor.usuario)
    respuesta = client.get(reverse("inicio"))
    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("mi_servicio")


def test_conductor_no_entra(client, conductor):
    """Un conductor no puede ver la flota: solo ve su propio servicio."""
    client.force_login(conductor.usuario)
    respuesta = client.get(reverse("flota:lista"))
    assert respuesta.status_code == 403


def test_admin_ve_la_lista(client, admin, vehiculo, documento_sin_soporte):
    client.force_login(admin)
    respuesta = client.get(reverse("flota:lista"))
    assert respuesta.status_code == 200
    assert b"ABC123" in respuesta.content
    assert b"1 sin soporte" in respuesta.content


def test_detalle_muestra_soporte_pendiente_y_seis_fotos(
    client, admin, vehiculo, documento_sin_soporte
):
    client.force_login(admin)
    respuesta = client.get(reverse("flota:detalle", args=[vehiculo.placa]))
    assert respuesta.status_code == 200
    contenido = respuesta.content.decode()
    assert "Soporte pendiente" in contenido
    # Un espacio por cada uno de los 6 tipos de foto, aunque estén vacíos.
    assert contenido.count("Sin foto") == 6
    assert "Tablero (kilometraje)" in contenido


def test_lista_documentos_filtra_pendientes(client, admin, vehiculo, documento_sin_soporte):
    client.force_login(admin)
    respuesta = client.get(reverse("documentos:lista"), {"soporte": "pendiente"})
    assert respuesta.status_code == 200
    assert b"ABC123" in respuesta.content
    assert b"Soporte pendiente" in respuesta.content


def test_login_usa_la_cedula(client):
    respuesta = client.get(reverse("login"))
    assert respuesta.status_code == 200
    assert b"C\xc3\xa9dula" in respuesta.content


def test_logout_vuelve_al_login(client, admin):
    client.force_login(admin)
    respuesta = client.post(reverse("logout"))
    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("login")
