"""Pruebas de los datos maestros: vehículos, conductores y usuarios (v0.4)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.flota.models import Conductor, Vehiculo
from apps.usuarios.models import Usuario

CLAVE = "ClaveSegura2026"


@pytest.fixture
def superadmin(db):
    return Usuario.objects.create_superuser(
        documento="900100100",
        email="jefe@ejemplo.com",
        password=CLAVE,
        first_name="Sara",
        last_name="Jefe",
    )


@pytest.fixture
def admin(db):
    return Usuario.objects.create_user(
        documento="800200200",
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


# ---------------------------------------------------------------------------
# Vehículos
# ---------------------------------------------------------------------------
def datos_vehiculo(**cambios):
    datos = {
        "placa": "XYZ789",
        "marca": "CHEVROLET",
        "referencia": "NHR",
        "modelo": 2018,
        "tipo_carroceria": "FURGON",
        "vin": "",
        "motor": "",
        "combustible": "diesel",
        "km_actual": 5000,
        "propietario": "",
    }
    datos.update(cambios)
    return datos


def test_el_admin_no_puede_crear_vehiculos(client, admin):
    client.force_login(admin)
    respuesta = client.post(reverse("maestros:vehiculo_nuevo"), datos_vehiculo())
    assert respuesta.status_code == 403
    assert not Vehiculo.objects.filter(placa="XYZ789").exists()


def test_el_superadmin_crea_un_vehiculo(client, superadmin):
    client.force_login(superadmin)
    respuesta = client.post(reverse("maestros:vehiculo_nuevo"), datos_vehiculo())
    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("flota:lista")
    assert Vehiculo.objects.filter(placa="XYZ789").exists()


def test_la_placa_se_guarda_en_mayusculas(client, superadmin):
    client.force_login(superadmin)
    client.post(reverse("maestros:vehiculo_nuevo"), datos_vehiculo(placa="xyz789"))
    assert Vehiculo.objects.filter(placa="XYZ789").exists()


def test_no_se_puede_bajar_el_kilometraje(client, superadmin, vehiculo):
    """R12: el kilometraje nunca disminuye, tampoco desde el formulario."""
    client.force_login(superadmin)
    respuesta = client.post(
        reverse("maestros:vehiculo_editar", args=[vehiculo.placa]),
        datos_vehiculo(placa=vehiculo.placa, km_actual=500),
    )
    assert respuesta.status_code == 200
    assert "no puede ser menor" in respuesta.content.decode()
    vehiculo.refresh_from_db()
    assert vehiculo.km_actual == 1000


def test_editar_un_vehiculo_vuelve_a_su_hoja_de_vida(client, superadmin, vehiculo):
    client.force_login(superadmin)
    respuesta = client.post(
        reverse("maestros:vehiculo_editar", args=[vehiculo.placa]),
        datos_vehiculo(placa=vehiculo.placa, km_actual=1500, propietario="Dueño de prueba"),
    )
    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("flota:detalle", args=[vehiculo.placa])
    vehiculo.refresh_from_db()
    assert vehiculo.km_actual == 1500


# ---------------------------------------------------------------------------
# Conductores
# ---------------------------------------------------------------------------
def datos_conductor(**cambios):
    datos = {
        "documento": "10203040",
        "first_name": "Carlos",
        "last_name": "Pérez",
        "email": "carlos@ejemplo.com",
        "telefono": "3001234567",
        "password1": CLAVE,
        "password2": CLAVE,
        "licencia_categoria": "c2",
        "licencia_vencimiento": (timezone.localdate() + timedelta(days=365)).isoformat(),
        "contacto_emergencia_nombre": "Marta",
        "contacto_emergencia_telefono": "3009999999",
    }
    datos.update(cambios)
    return datos


def test_crear_conductor_crea_tambien_su_usuario(client, superadmin):
    client.force_login(superadmin)
    respuesta = client.post(reverse("maestros:conductor_nuevo"), datos_conductor())
    assert respuesta.status_code == 302
    usuario = Usuario.objects.get(documento="10203040")
    assert usuario.rol == Usuario.Rol.CONDUCTOR
    assert usuario.check_password(CLAVE) is True
    conductor = Conductor.objects.get(usuario=usuario)
    assert conductor.licencia_categoria == "c2"
    assert conductor.estado == Conductor.Estado.ACTIVO


def test_no_se_repiten_cedulas(client, superadmin):
    client.force_login(superadmin)
    client.post(reverse("maestros:conductor_nuevo"), datos_conductor())
    respuesta = client.post(
        reverse("maestros:conductor_nuevo"),
        datos_conductor(email="otro@ejemplo.com"),
    )
    assert respuesta.status_code == 200
    assert "Ya hay un usuario con esa cédula" in respuesta.content.decode()
    assert Usuario.objects.filter(documento="10203040").count() == 1


def test_administrador_solo_consulta_conductores(client, admin, superadmin):
    client.force_login(superadmin)
    client.post(reverse("maestros:conductor_nuevo"), datos_conductor())
    client.force_login(admin)
    respuesta = client.get(reverse("conductores"))
    assert respuesta.status_code == 200
    contenido = respuesta.content.decode()
    assert "Carlos Pérez" in contenido
    # Sin botones de edición ni de baja.
    assert reverse("maestros:conductor_nuevo") not in contenido
    assert "Dar de baja" not in contenido


def test_baja_de_conductor_guarda_fecha_y_motivo(client, superadmin):
    """R20: la baja no borra nada y deja el registro inactivo."""
    client.force_login(superadmin)
    client.post(reverse("maestros:conductor_nuevo"), datos_conductor())
    conductor = Conductor.objects.get(usuario__documento="10203040")

    respuesta = client.post(
        reverse("maestros:conductor_baja", args=[conductor.pk]),
        {"fecha_baja": timezone.localdate().isoformat(), "motivo_baja": "Renuncia"},
    )
    assert respuesta.status_code == 302
    conductor.refresh_from_db()
    assert conductor.activo is False
    assert conductor.motivo_baja == "Renuncia"
    assert conductor.estado == Conductor.Estado.INACTIVO


def test_la_baja_no_acepta_fecha_futura(client, superadmin):
    client.force_login(superadmin)
    client.post(reverse("maestros:conductor_nuevo"), datos_conductor())
    conductor = Conductor.objects.get(usuario__documento="10203040")
    manana = (timezone.localdate() + timedelta(days=1)).isoformat()

    respuesta = client.post(
        reverse("maestros:conductor_baja", args=[conductor.pk]),
        {"fecha_baja": manana, "motivo_baja": "Prueba"},
    )
    assert respuesta.status_code == 200
    conductor.refresh_from_db()
    assert conductor.activo is True


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------
def test_el_superadmin_crea_un_administrador(client, superadmin):
    client.force_login(superadmin)
    respuesta = client.post(
        reverse("maestros:usuario_nuevo"),
        {
            "documento": "700300300",
            "first_name": "Luis",
            "last_name": "Mora",
            "email": "luis@ejemplo.com",
            "telefono": "",
            "rol": "admin",
            "telegram_chat_id": "123456",
            "password1": CLAVE,
            "password2": CLAVE,
        },
    )
    assert respuesta.status_code == 302
    usuario = Usuario.objects.get(documento="700300300")
    assert usuario.rol == Usuario.Rol.ADMIN
    assert usuario.telegram_chat_id == "123456"


def test_el_superadmin_no_puede_quitarse_su_propio_rol(client, superadmin):
    client.force_login(superadmin)
    respuesta = client.post(
        reverse("maestros:usuario_editar", args=[superadmin.pk]),
        {
            "documento": superadmin.documento,
            "first_name": superadmin.first_name,
            "last_name": superadmin.last_name,
            "email": superadmin.email,
            "telefono": "",
            "rol": "admin",
            "telegram_chat_id": "",
            "password1": "",
            "password2": "",
        },
    )
    assert respuesta.status_code == 200
    assert "No puedes quitarte tu propio rol" in respuesta.content.decode()
    superadmin.refresh_from_db()
    assert superadmin.rol == Usuario.Rol.SUPERADMIN
