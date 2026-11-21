"""Pruebas de las novedades (v0.7): estados, bloqueo R7, fotos y trazabilidad."""

from datetime import timedelta
from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from apps.flota.models import (
    Conductor,
    FotoNovedad,
    Gestion,
    Inspeccion,
    ItemInspeccion,
    Novedad,
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


@pytest.fixture
def inspeccion(db, vehiculo, conductor):
    plantilla = PlantillaInspeccion.objects.create(nombre="Rápida")
    item = ItemInspeccion.objects.create(
        plantilla=plantilla,
        grupo="Frenos y llantas",
        nombre="Frenos",
        es_critico=True,
        orden=1,
    )
    inspeccion = Inspeccion.objects.create(
        vehiculo=vehiculo, conductor=conductor, plantilla=plantilla, km=84_300
    )
    RespuestaItem.objects.create(
        inspeccion=inspeccion, item=item, estado=RespuestaItem.Estado.BUEN_ESTADO
    )
    return inspeccion


@pytest.fixture(autouse=True)
def media_temporal(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def png_valido():
    buffer = BytesIO()
    Image.new("RGB", (1, 1), "white").save(buffer, format="PNG")
    return SimpleUploadedFile("foto.png", buffer.getvalue(), content_type="image/png")


def novedad(vehiculo, severidad=Novedad.Severidad.MEDIA, **cambios):
    datos = {
        "vehiculo": vehiculo,
        "descripcion": "Fuga de aceite en el motor",
        "severidad": severidad,
    }
    datos.update(cambios)
    return Novedad.objects.create(**datos)


# --- Severidad y superadmin ---------------------------------------------------


def test_novedad_critica_requiere_superadmin(vehiculo):
    creada = novedad(
        vehiculo,
        severidad=Novedad.Severidad.CRITICA,
        requiere_superadmin=False,
    )

    assert creada.requiere_superadmin is True
    creada.refresh_from_db()
    assert creada.requiere_superadmin is True


def test_novedad_no_critica_no_requiere_superadmin(vehiculo):
    creada = novedad(vehiculo, severidad=Novedad.Severidad.ALTA)

    assert creada.requiere_superadmin is False


# --- Máquina de estados (contrato §8.1) --------------------------------------


def test_ciclo_valido_de_estados(vehiculo, admin):
    creada = novedad(vehiculo, severidad=Novedad.Severidad.ALTA)

    creada.cambiar_estado(Novedad.Estado.EN_PROCESO, usuario=admin)
    creada.cambiar_estado(Novedad.Estado.RESUELTA, usuario=admin)
    creada.cambiar_estado(Novedad.Estado.VALIDADA, usuario=admin)

    assert creada.estado == Novedad.Estado.VALIDADA
    assert creada.gestiones.count() == 3


def test_transicion_invalida_se_rechaza(vehiculo):
    creada = novedad(vehiculo)

    with pytest.raises(ValidationError, match="No se puede pasar"):
        creada.cambiar_estado(Novedad.Estado.VALIDADA)


def test_rechazar_desde_abierta_y_estado_terminal(vehiculo):
    creada = novedad(vehiculo, severidad=Novedad.Severidad.CRITICA)

    creada.cambiar_estado(Novedad.Estado.RECHAZADA)

    assert creada.estado == Novedad.Estado.RECHAZADA
    with pytest.raises(ValidationError):
        creada.cambiar_estado(Novedad.Estado.EN_PROCESO)


def test_gestion_guarda_usuario_y_descripcion(vehiculo, admin):
    creada = novedad(vehiculo)

    creada.cambiar_estado(
        Novedad.Estado.EN_PROCESO,
        usuario=admin,
        descripcion="Se revisa la fuga de aceite",
    )

    gestion = Gestion.objects.get(novedad=creada)
    assert gestion.usuario == admin
    assert gestion.descripcion == "Se revisa la fuga de aceite"


# --- R7: bloqueo del vehículo -------------------------------------------------


def test_novedad_critica_bloquea_el_vehiculo(vehiculo):
    creada = novedad(vehiculo, severidad=Novedad.Severidad.CRITICA)

    assert creada.bloquea_vehiculo is True
    assert vehiculo.estado == Vehiculo.Estado.BLOQUEADO_NOVEDAD
    assert Novedad.criticas_de(vehiculo).count() == 1


def test_validar_la_novedad_desbloquea_el_vehiculo(vehiculo):
    creada = novedad(vehiculo, severidad=Novedad.Severidad.CRITICA)
    assert vehiculo.estado == Vehiculo.Estado.BLOQUEADO_NOVEDAD

    creada.cambiar_estado(Novedad.Estado.EN_PROCESO)
    creada.cambiar_estado(Novedad.Estado.RESUELTA)
    creada.cambiar_estado(Novedad.Estado.VALIDADA)
    vehiculo.refresh_from_db()

    assert creada.bloquea_vehiculo is False
    assert vehiculo.estado == Vehiculo.Estado.OPERATIVO
    assert Novedad.criticas_de(vehiculo).count() == 0


def test_novedad_no_critica_no_bloquea(vehiculo):
    novedad(vehiculo, severidad=Novedad.Severidad.ALTA)

    assert vehiculo.estado == Vehiculo.Estado.OPERATIVO


# --- Creación desde la inspección (opción A) ----------------------------------


def test_inspeccion_bloqueada_crea_la_novedad(inspeccion):
    critica = inspeccion.respuestas.first()
    critica.estado = RespuestaItem.Estado.CON_NOVEDAD
    critica.informe = "Freno fundido"
    critica.foto = png_valido()
    critica.save()

    inspeccion.firmar(CLAVE)

    creada = Novedad.objects.get(inspeccion=inspeccion)
    assert creada.origen == Novedad.Origen.INSPECCION
    assert creada.severidad == Novedad.Severidad.CRITICA
    assert creada.estado == Novedad.Estado.ABIERTA
    assert creada.requiere_superadmin is True
    assert "Frenos" in creada.descripcion
    assert inspeccion.vehiculo.estado == Vehiculo.Estado.BLOQUEADO_NOVEDAD


def test_inspeccion_aprobada_no_crea_novedad(inspeccion):
    inspeccion.firmar(CLAVE)

    assert Novedad.objects.count() == 0
    assert inspeccion.vehiculo.estado == Vehiculo.Estado.OPERATIVO


def test_crear_novedad_desde_inspeccion_es_idempotente(inspeccion):
    primera = inspeccion.crear_novedad_desde_inspeccion()
    segunda = inspeccion.crear_novedad_desde_inspeccion()

    assert primera.pk == segunda.pk
    assert Novedad.objects.count() == 1


# --- Fotos opcionales ---------------------------------------------------------


def test_la_novedad_puede_tener_cero_una_o_varias_fotos(vehiculo):
    creada = novedad(vehiculo)

    assert creada.fotos.count() == 0
    FotoNovedad.objects.create(novedad=creada, imagen=png_valido())
    assert creada.fotos.count() == 1
    FotoNovedad.objects.create(novedad=creada, imagen=png_valido())

    nombres = list(creada.fotos.values_list("imagen", flat=True))
    assert len(nombres) == 2
    assert any(n.endswith("ABC123-1.png") for n in nombres)
    assert any(n.endswith("ABC123-2.png") for n in nombres)
