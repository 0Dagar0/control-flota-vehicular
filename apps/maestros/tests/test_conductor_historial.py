"""Pruebas del historial del conductor (integración del encargo 03)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.flota.models import Asignacion, Conductor, Documento, Servicio, Vehiculo
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
        email="carlos@ejemplo.com",
        password=CLAVE,
        first_name="Carlos",
        last_name="Pérez",
        rol=Usuario.Rol.CONDUCTOR,
        telefono="3001234567",
    )
    return Conductor.objects.create(
        usuario=usuario,
        licencia_categoria=Conductor.CategoriaLicencia.C1,
        licencia_vencimiento=timezone.localdate() + timedelta(days=200),
        contacto_emergencia_nombre="Marta Pérez",
        contacto_emergencia_telefono="3009999999",
    )


@pytest.fixture
def vehiculo(db):
    return Vehiculo.objects.create(
        placa="ABC123", marca="FOTON", referencia="BJ1044", modelo=2025, km_actual=1400
    )


def test_el_admin_ve_asignaciones_servicios_y_documentos(
    client, admin, conductor, vehiculo
):
    asignacion = Asignacion.objects.create(
        vehiculo=vehiculo, conductor=conductor, creado_por=admin
    )
    Servicio.objects.create(
        vehiculo=vehiculo,
        conductor=conductor,
        km_inicial=1200,
        km_final=1300,
        ruta="Reparto norte",
        cerrado_en=timezone.now(),
    )
    Servicio.objects.create(
        vehiculo=vehiculo,
        conductor=conductor,
        km_inicial=1300,
        km_final=1400,
        ruta="Reparto sur",
        cerrado_en=timezone.now(),
        sin_novedad=False,
        observacion_cierre="Fuga de aceite",
    )
    Documento.objects.create(
        tipo=Documento.Tipo.LICENCIA,
        conductor=conductor,
        entidad="Secretaría de Movilidad",
        numero="10203040",
        vencimiento=conductor.licencia_vencimiento,
    )

    client.force_login(admin)
    contenido = client.get(
        reverse("maestros:conductor_historial", args=[conductor.pk])
    ).content.decode()

    assert "Carlos Pérez" in contenido
    assert "ABC123" in contenido
    assert "Asignación actual" in contenido
    assert "200" in contenido  # km recorridos en los dos servicios
    assert "Con novedad" in contenido
    assert "Fuga de aceite" in contenido
    assert "Licencia de conducción" in contenido
    assert "Marta Pérez" in contenido
    assert asignacion.vehiculo.placa in contenido


def test_la_baja_no_borra_el_historial(client, admin, conductor):
    conductor.activo = False
    conductor.fecha_baja = timezone.localdate()
    conductor.motivo_baja = "Terminación de contrato"
    conductor.save()

    client.force_login(admin)
    contenido = client.get(
        reverse("maestros:conductor_historial", args=[conductor.pk])
    ).content.decode()

    assert "Conductador dado de baja" not in contenido
    assert "Conductor dado de baja" in contenido
    assert "Terminación de contrato" in contenido
    assert "Este conductor nunca ha tenido un vehículo asignado" in contenido


def test_el_conductor_no_ve_el_historial(client, conductor):
    client.force_login(conductor.usuario)
    respuesta = client.get(reverse("maestros:conductor_historial", args=[conductor.pk]))
    assert respuesta.status_code == 403
