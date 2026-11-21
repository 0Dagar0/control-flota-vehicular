"""Pruebas del panel de indicadores y la hoja de vida 360° (v0.10)."""

from datetime import timedelta
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.flota.models import (
    Conductor,
    Documento,
    FotoVehiculo,
    Inspeccion,
    ItemInspeccion,
    Novedad,
    PlantillaInspeccion,
    Vehiculo,
)
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
def conductor(db):
    usuario = Usuario.objects.create_user(
        documento="10203040",
        email="carlos@ejemplo.com",
        password=CLAVE,
        first_name="Carlos",
        last_name="Pérez",
        rol=Usuario.Rol.CONDUCTOR,
    )
    return Conductor.objects.create(
        usuario=usuario,
        licencia_vencimiento=timezone.localdate() + timedelta(days=365),
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


@pytest.fixture(autouse=True)
def media_temporal(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def png_valido():
    buffer = BytesIO()
    Image.new("RGB", (1, 1), "white").save(buffer, format="PNG")
    return SimpleUploadedFile("frontal.png", buffer.getvalue(), content_type="image/png")


def test_cumplimiento_documental_usa_el_soporte(vehiculo):
    Documento.objects.create(
        tipo=Documento.Tipo.SOAT,
        vehiculo=vehiculo,
        vencimiento=timezone.localdate() + timedelta(days=100),
        soporte="documentos/soat.pdf",
    )
    Documento.objects.create(
        tipo=Documento.Tipo.POLIZA,
        vehiculo=vehiculo,
        vencimiento=timezone.localdate() + timedelta(days=100),
    )

    assert vehiculo.cumplimiento_documental == 50


def test_vehiculo_sin_documentos_tiene_cumplimiento_completo(vehiculo):
    assert vehiculo.cumplimiento_documental == 100


def test_el_admin_ve_el_panel(client, admin, vehiculo):
    client.force_login(admin)

    respuesta = client.get(reverse("panel"))

    assert respuesta.status_code == 200
    contenido = respuesta.content.decode()
    assert "Panel de indicadores" in contenido
    assert "Cumplimiento documental" in contenido
    assert "ABC123" in contenido


def test_el_conductor_no_entra_al_panel(client, conductor):
    client.force_login(conductor.usuario)

    respuesta = client.get(reverse("panel"))

    assert respuesta.status_code == 403


def test_las_fallas_repetidas_aparecen_en_el_panel(client, admin, vehiculo):
    Novedad.objects.create(
        vehiculo=vehiculo,
        descripcion="Freno fundido",
        severidad=Novedad.Severidad.ALTA,
    )
    Novedad.objects.create(
        vehiculo=vehiculo,
        descripcion="freno fundido",
        severidad=Novedad.Severidad.ALTA,
    )
    client.force_login(admin)

    respuesta = client.get(reverse("panel"))

    contenido = respuesta.content.decode()
    assert "freno fundido" in contenido
    assert "Fallas repetidas" in contenido


def test_la_vista_360_muestra_todas_las_secciones(
    client, admin, vehiculo, conductor
):
    Documento.objects.create(
        tipo=Documento.Tipo.SOAT,
        vehiculo=vehiculo,
        vencimiento=timezone.localdate() + timedelta(days=2),
    )
    Novedad.objects.create(vehiculo=vehiculo, descripcion="Fuga de aceite")
    FotoVehiculo.objects.create(
        vehiculo=vehiculo, tipo=FotoVehiculo.Tipo.FRONTAL, imagen=png_valido()
    )
    plantilla = PlantillaInspeccion.objects.create(nombre="Rápida")
    ItemInspeccion.objects.create(plantilla=plantilla, nombre="Frenos")
    Inspeccion.objects.create(
        vehiculo=vehiculo, conductor=conductor, plantilla=plantilla, km=84_300
    )
    client.force_login(admin)

    respuesta = client.get(reverse("hoja_vida_360", args=["ABC123"]))

    assert respuesta.status_code == 200
    contenido = respuesta.content.decode()
    assert "Vista 360°" in contenido
    assert "Documentos (semáforo 30/15/7/3/0)" in contenido
    assert "Fuga de aceite" in contenido
    assert "3 días" in contenido
    assert "frontal" in contenido


def test_la_vista_360_con_placa_inexistente_da_404(client, admin):
    client.force_login(admin)

    respuesta = client.get(reverse("hoja_vida_360", args=["ZZZ999"]))

    assert respuesta.status_code == 404
