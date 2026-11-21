"""Pruebas del semáforo de documentos y la renovación (v0.9)."""

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
        documento="800200200",
        email="admin@ejemplo.com",
        password=CLAVE,
        first_name="Marcela",
        last_name="Díaz",
        rol=Usuario.Rol.ADMIN,
    )


@pytest.fixture
def vehiculo(db):
    return Vehiculo.objects.create(
        placa="ABC123",
        marca="Renault",
        referencia="Kangoo",
        modelo=2021,
        km_actual=84_300,
    )


def documento(vehiculo, dias):
    return Documento.objects.create(
        tipo=Documento.Tipo.SOAT,
        vehiculo=vehiculo,
        entidad="Aseguradora de prueba",
        numero="SOAT-001",
        vencimiento=timezone.localdate() + timedelta(days=dias),
    )


@pytest.mark.parametrize(
    ("dias", "nivel", "color"),
    [
        (-1, "vencido", "rojo"),
        (0, "hoy", "rojo"),
        (1, "tres", "rojo"),
        (3, "tres", "rojo"),
        (4, "siete", "amarillo"),
        (7, "siete", "amarillo"),
        (8, "quince", "amarillo"),
        (15, "quince", "amarillo"),
        (16, "treinta", "verde"),
        (30, "treinta", "verde"),
        (31, "vigente", "verde"),
    ],
)
def test_semaforo_por_niveles(vehiculo, dias, nivel, color):
    creado = documento(vehiculo, dias)

    assert creado.semaforo == nivel
    assert creado.semaforo_color == color
    assert creado.semaforo_etiqueta


# --- Renovación ---------------------------------------------------------------


def test_admin_renueva_un_documento(client, admin, vehiculo):
    vencido = documento(vehiculo, -5)
    client.force_login(admin)
    nuevo = (timezone.localdate() + timedelta(days=180)).isoformat()

    respuesta = client.post(
        reverse("documentos:renovar", args=[vencido.pk]),
        {
            "entidad": "Nueva aseguradora",
            "numero": "SOAT-2027",
            "vencimiento": nuevo,
        },
    )

    assert respuesta.status_code == 302
    vencido.refresh_from_db()
    assert vencido.entidad == "Nueva aseguradora"
    assert vencido.numero == "SOAT-2027"
    assert vencido.vencimiento == timezone.localdate() + timedelta(days=180)
    assert vencido.semaforo == "vigente"


def test_la_renovacion_rechaza_una_fecha_pasada(client, admin, vehiculo):
    vencido = documento(vehiculo, -5)
    client.force_login(admin)

    respuesta = client.post(
        reverse("documentos:renovar", args=[vencido.pk]),
        {
            "entidad": "Aseguradora",
            "numero": "SOAT-001",
            "vencimiento": (timezone.localdate() - timedelta(days=1)).isoformat(),
        },
    )

    assert respuesta.status_code == 200
    assert "fecha futura" in respuesta.content.decode()
    vencido.refresh_from_db()
    assert vencido.vencimiento == timezone.localdate() - timedelta(days=5)


def test_el_conductor_no_puede_renovar(client, vehiculo):
    vencido = documento(vehiculo, -5)
    usuario = Usuario.objects.create_user(
        documento="10203040",
        email="carlos@ejemplo.com",
        password=CLAVE,
        rol=Usuario.Rol.CONDUCTOR,
    )
    Conductor.objects.create(
        usuario=usuario,
        licencia_vencimiento=timezone.localdate() + timedelta(days=365),
    )
    client.force_login(usuario)

    respuesta = client.get(reverse("documentos:renovar", args=[vencido.pk]))

    assert respuesta.status_code == 403


# --- Alertas de 0 y 3 días ----------------------------------------------------


def test_alertas_incluyen_vencimientos_de_hoy_y_tres_dias(client, admin, vehiculo):
    documento(vehiculo, 0)
    documento(vehiculo, 3)
    client.force_login(admin)

    respuesta = client.get(reverse("alertas"))

    contenido = respuesta.content.decode()
    assert "SOAT vence hoy" in contenido
    assert "SOAT por vencer en 3 días" in contenido
