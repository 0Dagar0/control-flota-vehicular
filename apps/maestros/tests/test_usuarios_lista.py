"""Pruebas del listado de usuarios rediseñado (integración del encargo 03)."""

import pytest
from django.urls import reverse

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
        telegram_chat_id="12345",
    )


@pytest.fixture
def conductor_usuario(db):
    return Usuario.objects.create_user(
        documento="700300300",
        email="carlos@ejemplo.com",
        password=CLAVE,
        first_name="Carlos",
        last_name="Pérez",
        is_active=False,
    )


def test_el_superadmin_ve_roles_telegram_y_contrasenas_enmascaradas(
    client, superadmin, admin, conductor_usuario
):
    client.force_login(superadmin)
    contenido = client.get(reverse("maestros:usuario_lista")).content.decode()

    assert "Usuarios y roles" in contenido
    assert "superadmin" in contenido
    assert "admin" in contenido
    assert "conductor" in contenido
    assert "Vinculado" in contenido
    assert "Sin vincular" in contenido
    assert "Inactivo" in contenido
    assert "••••••••" in contenido
    assert "Última conexión" in contenido
    assert "No puedes cambiar tu propio rol" in contenido


def test_los_filtros_reducen_la_lista(client, superadmin, admin, conductor_usuario):
    client.force_login(superadmin)
    url = reverse("maestros:usuario_lista")

    contenido = client.get(url, {"rol": "conductor", "estado": "inactivo"}).content.decode()
    assert "Carlos Pérez" in contenido
    assert "Ana Rojas" not in contenido

    contenido = client.get(url, {"buscar": "admin@"}).content.decode()
    assert "Ana Rojas" in contenido
    assert "Carlos Pérez" not in contenido
    # Los indicadores siguen contando a todos los usuarios, no solo a los filtrados.
    assert "<strong>3</strong>" in contenido


def test_el_admin_no_entra_a_usuarios(client, admin):
    client.force_login(admin)
    respuesta = client.get(reverse("maestros:usuario_lista"))
    assert respuesta.status_code == 403
