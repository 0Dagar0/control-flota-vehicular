"""Datos compartidos por las pruebas de notificaciones (v1.0)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.flota.models import Conductor, Vehiculo
from apps.usuarios.models import Usuario

from ..models import Canal, Estado, Notificacion

CLAVE = "ClaveSegura2026"


@pytest.fixture
def admin(db):
    return Usuario.objects.create_user(
        documento="800300100",
        email="admin@ejemplo.com",
        password=CLAVE,
        first_name="Marcela",
        last_name="Díaz",
        rol=Usuario.Rol.ADMIN,
    )


@pytest.fixture
def superadmin(db):
    return Usuario.objects.create_user(
        documento="800300101",
        email="jefe@ejemplo.com",
        password=CLAVE,
        first_name="Andrés",
        last_name="Salazar",
        rol=Usuario.Rol.SUPERADMIN,
    )


@pytest.fixture
def conductor(db):
    usuario = Usuario.objects.create_user(
        documento="10203041",
        email="carlos@ejemplo.com",
        password=CLAVE,
        first_name="Carlos",
        last_name="Pérez",
        rol=Usuario.Rol.CONDUCTOR,
        telegram_chat_id="111222333",
    )
    return Conductor.objects.create(
        usuario=usuario,
        licencia_vencimiento=timezone.localdate() + timedelta(days=300),
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


@pytest.fixture
def notificacion(admin):
    return Notificacion.objects.create(
        usuario=admin,
        evento="novedad_critica",
        canal=Canal.CORREO,
        titulo="Novedad crítica en ABC123",
        mensaje="Fuga de aceite en el motor.",
        referencia="novedad:1",
        clave="novedad:1",
        estado=Estado.PENDIENTE,
    )
