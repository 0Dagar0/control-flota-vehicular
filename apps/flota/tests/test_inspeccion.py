"""Pruebas de la inspección rápida (v0.6): plantilla, firma PIN y bloqueo.

Cubre las reglas R3, R5, R6 y R7 del documento maestro y el contrato aprobado
de la plantilla «Rápida» (7 ítems en 4 grupos, documentado en
``Avances/maquetas/LEEME-inspeccion-rapida.md``).
"""

from datetime import timedelta
from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.utils import timezone
from PIL import Image

from apps.flota.models import (
    Conductor,
    Inspeccion,
    ItemInspeccion,
    PlantillaInspeccion,
    RespuestaItem,
    Vehiculo,
)
from apps.usuarios.models import Usuario

CLAVE = "ClaveSegura2026"

ITEMS = (
    ("Luces y visibilidad", "Luces delanteras", True, True),
    ("Luces y visibilidad", "Luces traseras", True, True),
    ("Motor y fluidos", "Nivel de aceite", True, True),
    ("Frenos y llantas", "Frenos", True, True),
    ("Frenos y llantas", "Llantas", True, True),
    ("Seguridad a bordo", "Kit de carretera", False, False),
    ("Seguridad a bordo", "Botiquín", False, False),
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


@pytest.fixture
def plantilla(db):
    plantilla = PlantillaInspeccion.objects.create(
        nombre="Rápida", nivel=PlantillaInspeccion.Nivel.RAPIDA
    )
    for orden, (grupo, nombre, critico, foto) in enumerate(ITEMS, start=1):
        ItemInspeccion.objects.create(
            plantilla=plantilla,
            grupo=grupo,
            nombre=nombre,
            es_critico=critico,
            requiere_foto=foto,
            orden=orden,
        )
    return plantilla


@pytest.fixture
def inspeccion(db, vehiculo, conductor, plantilla):
    return Inspeccion.objects.create(
        vehiculo=vehiculo, conductor=conductor, plantilla=plantilla, km=84_300
    )


@pytest.fixture(autouse=True)
def media_temporal(settings, tmp_path):
    """Las fotos de prueba van a una carpeta temporal, no al proyecto."""
    settings.MEDIA_ROOT = tmp_path


def png_valido():
    buffer = BytesIO()
    Image.new("RGB", (1, 1), "white").save(buffer, format="PNG")
    return SimpleUploadedFile("foto.png", buffer.getvalue(), content_type="image/png")


def responder_todos(inspeccion, estado=RespuestaItem.Estado.BUEN_ESTADO):
    for item in inspeccion.plantilla.items.all():
        RespuestaItem.objects.create(inspeccion=inspeccion, item=item, estado=estado)


def marcar(inspeccion, item, estado):
    RespuestaItem.objects.filter(inspeccion=inspeccion, item=item).update(estado=estado)


# --- Plantilla aprobada -------------------------------------------------------


def test_plantilla_rapida_tiene_siete_items_en_cuatro_grupos(plantilla):
    assert plantilla.items.count() == 7
    assert set(plantilla.items.values_list("grupo", flat=True)) == {
        "Luces y visibilidad",
        "Motor y fluidos",
        "Frenos y llantas",
        "Seguridad a bordo",
    }
    assert plantilla.items.filter(es_critico=True).count() == 5


# --- Resultado y bloqueo ------------------------------------------------------


def test_resultado_aprobada_cuando_todo_esta_en_buen_estado(inspeccion):
    responder_todos(inspeccion)

    assert inspeccion.calcular_resultado() == Inspeccion.Resultado.APROBADA
    inspeccion.firmar(CLAVE)

    assert inspeccion.finalizada is True
    assert inspeccion.resultado == Inspeccion.Resultado.APROBADA


def test_novedad_en_item_critico_bloquea(inspeccion):
    responder_todos(inspeccion)
    critico = inspeccion.plantilla.items.filter(es_critico=True).first()
    marcar(inspeccion, critico, RespuestaItem.Estado.CON_NOVEDAD)

    assert inspeccion.calcular_resultado() == Inspeccion.Resultado.BLOQUEADA
    inspeccion.firmar(CLAVE)
    assert inspeccion.resultado == Inspeccion.Resultado.BLOQUEADA


def test_novedad_no_critica_no_bloquea(inspeccion):
    responder_todos(inspeccion)
    no_critico = inspeccion.plantilla.items.filter(es_critico=False).first()
    marcar(inspeccion, no_critico, RespuestaItem.Estado.CON_NOVEDAD)

    assert inspeccion.calcular_resultado() == Inspeccion.Resultado.APROBADA


def test_inspeccion_bloqueada_deja_el_vehiculo_bloqueado(inspeccion, vehiculo):
    responder_todos(inspeccion)
    critico = inspeccion.plantilla.items.filter(es_critico=True).first()
    marcar(inspeccion, critico, RespuestaItem.Estado.CON_NOVEDAD)

    inspeccion.firmar(CLAVE)
    vehiculo.refresh_from_db()

    assert vehiculo.estado == Vehiculo.Estado.BLOQUEADO_NOVEDAD


def test_aprobada_hoy_solo_para_el_vehiculo_y_la_fecha(inspeccion, vehiculo):
    responder_todos(inspeccion)
    assert Inspeccion.aprobada_hoy(vehiculo) is False

    inspeccion.firmar(CLAVE)
    assert Inspeccion.aprobada_hoy(vehiculo) is True

    otro = Vehiculo.objects.create(
        placa="XYZ789", marca="FOTON", referencia="NHR", modelo=2020, km_actual=100
    )
    assert Inspeccion.aprobada_hoy(otro) is False


# --- R5: foto obligatoria -----------------------------------------------------


def test_item_con_novedad_exige_foto(inspeccion):
    respuesta = RespuestaItem(
        inspeccion=inspeccion,
        item=inspeccion.plantilla.items.first(),
        estado=RespuestaItem.Estado.CON_NOVEDAD,
    )

    with pytest.raises(ValidationError) as error:
        respuesta.full_clean()

    assert "foto" in error.value.message_dict


def test_item_con_novedad_y_foto_pasa_la_validacion(inspeccion):
    respuesta = RespuestaItem(
        inspeccion=inspeccion,
        item=inspeccion.plantilla.items.first(),
        estado=RespuestaItem.Estado.CON_NOVEDAD,
        foto=png_valido(),
    )

    respuesta.full_clean()


def test_item_en_buen_estado_no_exige_foto(inspeccion):
    respuesta = RespuestaItem(
        inspeccion=inspeccion,
        item=inspeccion.plantilla.items.first(),
        estado=RespuestaItem.Estado.BUEN_ESTADO,
    )

    respuesta.full_clean()


# --- R6: firma con PIN --------------------------------------------------------


def test_pin_incorrecto_no_firma(inspeccion):
    responder_todos(inspeccion)

    with pytest.raises(ValidationError) as error:
        inspeccion.firmar("clave-erronea")

    assert "firma_pin" in error.value.message_dict
    inspeccion.refresh_from_db()
    assert inspeccion.finalizada is False
    assert inspeccion.firma_en is None


def test_pin_correcto_firma_sin_guardar_la_contraseña(inspeccion):
    responder_todos(inspeccion)

    inspeccion.firmar(CLAVE)
    inspeccion.refresh_from_db()

    assert inspeccion.firma_en is not None
    assert inspeccion.finalizado_en is not None
    assert inspeccion.duracion is not None
    assert inspeccion.firmada_por is None
    assert inspeccion.conductor.usuario.check_password(CLAVE) is True
    assert not hasattr(inspeccion, "firma_pin")


def test_no_se_puede_firmar_sin_respuestas(inspeccion):
    with pytest.raises(ValidationError, match="no tiene respuestas"):
        inspeccion.firmar(CLAVE)


def test_no_se_puede_firmar_con_items_sin_revisar(inspeccion):
    responder_todos(inspeccion, estado=RespuestaItem.Estado.SIN_REVISAR)

    with pytest.raises(ValidationError, match="sin revisar"):
        inspeccion.firmar(CLAVE)


def test_no_se_puede_firmar_dos_veces(inspeccion):
    responder_todos(inspeccion)
    inspeccion.firmar(CLAVE)

    with pytest.raises(ValidationError, match="ya está finalizada"):
        inspeccion.firmar(CLAVE)


def test_un_item_solo_se_puede_responder_una_vez(inspeccion):
    item = inspeccion.plantilla.items.first()
    RespuestaItem.objects.create(inspeccion=inspeccion, item=item)

    with pytest.raises(IntegrityError):
        RespuestaItem.objects.create(inspeccion=inspeccion, item=item)
