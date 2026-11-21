"""Pruebas de las rutas de novedades (v0.7, tanda 2)."""

from datetime import timedelta
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.flota.models import Asignacion, Conductor, Novedad, Vehiculo
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


@pytest.fixture
def asignacion(conductor, vehiculo, db):
    return Asignacion.objects.create(vehiculo=vehiculo, conductor=conductor)


@pytest.fixture(autouse=True)
def media_temporal(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def png(nombre="foto.png"):
    buffer = BytesIO()
    Image.new("RGB", (1, 1), "white").save(buffer, format="PNG")
    return SimpleUploadedFile(nombre, buffer.getvalue(), content_type="image/png")


def reportar(client, conductor, **extra):
    client.force_login(conductor.usuario)
    datos = {
        "descripcion": "Fuga de aceite en el motor",
        "severidad": Novedad.Severidad.MEDIA,
        **extra,
    }
    return client.post(reverse("novedad_nueva"), datos)


# --- Reporte del conductor ----------------------------------------------------


def test_reportar_con_varias_fotos(client, conductor, asignacion):
    respuesta = reportar(
        client,
        conductor,
        fotos=[png("uno.png"), png("dos.png")],
    )

    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("mis_novedades")
    creada = Novedad.objects.get(conductor=conductor)
    assert creada.vehiculo == asignacion.vehiculo
    assert creada.origen == Novedad.Origen.REPORTE
    assert creada.estado == Novedad.Estado.ABIERTA
    assert creada.fotos.count() == 2


def test_reportar_sin_fotos_tambien_funciona(client, conductor, asignacion):
    respuesta = reportar(client, conductor)

    assert respuesta.status_code == 302
    assert Novedad.objects.get(conductor=conductor).fotos.count() == 0


def test_sin_vehiculo_asignado_no_se_puede_reportar(client, conductor):
    respuesta = reportar(client, conductor)

    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("mi_servicio")
    assert Novedad.objects.count() == 0


# --- Bandeja del administrador ------------------------------------------------


def test_admin_ve_la_bandeja_y_puede_filtrar(client, admin, vehiculo, conductor):
    Novedad.objects.create(
        vehiculo=vehiculo, conductor=conductor, descripcion="Prueba abierta",
        severidad=Novedad.Severidad.ALTA,
    )
    Novedad.objects.create(
        vehiculo=vehiculo, conductor=conductor, descripcion="Prueba resuelta",
        severidad=Novedad.Severidad.BAJA, estado=Novedad.Estado.RESUELTA,
    )
    client.force_login(admin)

    respuesta = client.get(reverse("novedades"), {"estado": "ABIERTA"})

    assert respuesta.status_code == 200
    contenido = respuesta.content.decode()
    assert "Prueba abierta" in contenido
    assert "Prueba resuelta" not in contenido


def test_el_conductor_no_entra_a_la_bandeja(client, conductor):
    client.force_login(conductor.usuario)

    respuesta = client.get(reverse("novedades"))

    assert respuesta.status_code == 403


# --- Gestión de estados -------------------------------------------------------


def test_admin_cambia_el_estado_y_queda_registrado(client, admin, vehiculo, conductor):
    creada = Novedad.objects.create(
        vehiculo=vehiculo, conductor=conductor, descripcion="Fuga de aceite"
    )
    client.force_login(admin)

    respuesta = client.post(
        reverse("novedad_gestion", args=[creada.pk]),
        {"estado": "EN_PROCESO", "descripcion": "Se revisa la fuga"},
    )

    assert respuesta.status_code == 302
    creada.refresh_from_db()
    assert creada.estado == Novedad.Estado.EN_PROCESO
    gestion = creada.gestiones.get()
    assert gestion.usuario == admin
    assert gestion.descripcion == "Se revisa la fuga"


def test_la_vista_rechaza_una_transicion_invalida(client, admin, vehiculo, conductor):
    creada = Novedad.objects.create(
        vehiculo=vehiculo, conductor=conductor, descripcion="Fuga de aceite"
    )
    client.force_login(admin)

    respuesta = client.post(
        reverse("novedad_gestion", args=[creada.pk]),
        {"estado": "VALIDADA", "descripcion": "Saltar pasos"},
    )

    assert respuesta.status_code == 200
    creada.refresh_from_db()
    assert creada.estado == Novedad.Estado.ABIERTA
    assert creada.gestiones.count() == 0


# --- Mis novedades y alertas --------------------------------------------------


def test_mis_novedades_solo_muestra_las_propias(client, conductor, vehiculo, admin):
    Novedad.objects.create(
        vehiculo=vehiculo, conductor=conductor, descripcion="Novedad propia"
    )
    otro = Conductor.objects.create(
        usuario=Usuario.objects.create_user(
            documento="50607080", email="otro@ejemplo.com", password=CLAVE
        ),
        licencia_vencimiento=timezone.localdate() + timedelta(days=365),
    )
    Novedad.objects.create(
        vehiculo=vehiculo, conductor=otro, descripcion="Novedad ajena"
    )
    client.force_login(conductor.usuario)

    respuesta = client.get(reverse("mis_novedades"))

    contenido = respuesta.content.decode()
    assert "Novedad propia" in contenido
    assert "Novedad ajena" not in contenido


def test_las_alertas_incluyen_la_novedad_critica(client, admin, vehiculo, conductor):
    Novedad.objects.create(
        vehiculo=vehiculo,
        conductor=conductor,
        descripcion="Freno fundido",
        severidad=Novedad.Severidad.CRITICA,
    )
    client.force_login(admin)

    respuesta = client.get(reverse("alertas"))

    assert respuesta.status_code == 200
    assert "Novedad crítica sin validar" in respuesta.content.decode()
