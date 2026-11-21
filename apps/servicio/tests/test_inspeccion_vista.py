"""Pruebas de la ruta de inspección rápida (v0.6, contrato §5.1)."""

from datetime import timedelta
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.flota.models import (
    Asignacion,
    Conductor,
    Inspeccion,
    PlantillaInspeccion,
    RespuestaItem,
    Vehiculo,
)
from apps.usuarios.models import Usuario

CLAVE = "ClaveSegura2026"


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


@pytest.fixture
def asignacion(conductor, vehiculo, db):
    return Asignacion.objects.create(vehiculo=vehiculo, conductor=conductor)


@pytest.fixture(autouse=True)
def plantilla(db):
    call_command("cargar_plantilla_inspeccion")


@pytest.fixture(autouse=True)
def media_temporal(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def url_inspeccion(placa="ABC123"):
    return reverse("inspeccion_rapida", args=[placa])


def datos_items(estado=RespuestaItem.Estado.BUEN_ESTADO):
    plantilla = PlantillaInspeccion.objects.get(nombre="Rápida")
    datos = {"firma_pin": CLAVE}
    for item in plantilla.items.all():
        datos[f"estado-{item.pk}"] = estado
    return datos


def png_valido():
    buffer = BytesIO()
    Image.new("RGB", (1, 1), "white").save(buffer, format="PNG")
    return SimpleUploadedFile("foto.png", buffer.getvalue(), content_type="image/png")


def test_el_get_muestra_los_siete_items_y_crea_la_inspeccion(
    client, conductor, asignacion
):
    client.force_login(conductor.usuario)

    respuesta = client.get(url_inspeccion())

    assert respuesta.status_code == 200
    contenido = respuesta.content.decode()
    assert "Luces delanteras" in contenido
    assert "Botiquín" in contenido
    assert Inspeccion.objects.filter(vehiculo=asignacion.vehiculo).count() == 1


def test_post_con_pin_correcto_registra_la_inspeccion_aprobada(
    client, conductor, asignacion
):
    client.force_login(conductor.usuario)

    respuesta = client.post(url_inspeccion(), datos_items())

    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("mi_servicio")
    inspeccion = Inspeccion.objects.get(vehiculo=asignacion.vehiculo)
    assert inspeccion.resultado == Inspeccion.Resultado.APROBADA
    assert inspeccion.respuestas.count() == 7
    assert Inspeccion.aprobada_hoy(asignacion.vehiculo) is True


def test_novedad_sin_foto_muestra_error_y_no_cierra(
    client, conductor, asignacion
):
    plantilla = PlantillaInspeccion.objects.get(nombre="Rápida")
    datos = datos_items()
    critico = plantilla.items.filter(es_critico=True).first()
    datos[f"estado-{critico.pk}"] = RespuestaItem.Estado.CON_NOVEDAD
    client.force_login(conductor.usuario)

    respuesta = client.post(url_inspeccion(), datos)

    assert respuesta.status_code == 200
    assert "foto" in respuesta.content.decode().lower()
    assert Inspeccion.objects.get(vehiculo=asignacion.vehiculo).finalizada is False


def test_pin_incorrecto_no_cierra_la_inspeccion(client, conductor, asignacion):
    datos = datos_items()
    datos["firma_pin"] = "clave-erronea"
    client.force_login(conductor.usuario)

    respuesta = client.post(url_inspeccion(), datos)

    assert respuesta.status_code == 200
    assert "contraseña" in respuesta.content.decode().lower()
    assert Inspeccion.objects.get(vehiculo=asignacion.vehiculo).finalizada is False


def test_novedad_critica_con_foto_bloquea_el_vehiculo(client, conductor, asignacion):
    plantilla = PlantillaInspeccion.objects.get(nombre="Rápida")
    datos = datos_items()
    critico = plantilla.items.filter(es_critico=True).first()
    datos[f"estado-{critico.pk}"] = RespuestaItem.Estado.CON_NOVEDAD
    datos[f"foto-{critico.pk}"] = png_valido()
    client.force_login(conductor.usuario)

    respuesta = client.post(url_inspeccion(), datos)

    assert respuesta.status_code == 302
    inspeccion = Inspeccion.objects.get(vehiculo=asignacion.vehiculo)
    assert inspeccion.resultado == Inspeccion.Resultado.BLOQUEADA
    asignacion.vehiculo.refresh_from_db()
    assert asignacion.vehiculo.estado == Vehiculo.Estado.BLOQUEADO_NOVEDAD


def test_no_se_puede_inspeccionar_la_placa_de_otro(client, conductor, asignacion):
    client.force_login(conductor.usuario)

    respuesta = client.get(url_inspeccion("XYZ789"))

    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("mi_servicio")
    assert Inspeccion.objects.count() == 0
