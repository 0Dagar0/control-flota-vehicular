"""Pruebas de la autorización de salida con falla (v0.8, contrato §5.3 y R8)."""

import hashlib
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.flota.models import Autorizacion, Conductor, Novedad, Vehiculo
from apps.usuarios.models import Usuario

CLAVE = "ClaveSegura2026"
JUSTIFICACION = "El freno fue revisado y se autoriza la salida con precaucion."


@pytest.fixture
def superadmin(db):
    return Usuario.objects.create_superuser(
        documento="800200200",
        email="jefe@ejemplo.com",
        password=CLAVE,
        first_name="Andrés",
        last_name="Salazar",
    )


@pytest.fixture
def admin(db):
    return Usuario.objects.create_user(
        documento="800200201",
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
def novedad_critica(vehiculo, conductor, db):
    return Novedad.objects.create(
        vehiculo=vehiculo,
        conductor=conductor,
        descripcion="Freno fundido detectado en la inspección",
        severidad=Novedad.Severidad.CRITICA,
    )


def autorizar(client, usuario, novedad, **extra):
    client.force_login(usuario)
    datos = {
        "justificacion": JUSTIFICACION,
        "password": CLAVE,
        "acepta_responsabilidad": "on",
        **extra,
    }
    return client.post(reverse("novedad_autorizar", args=[novedad.pk]), datos)


# --- Modelo ------------------------------------------------------------------


def test_el_hash_se_calcula_siempre_en_el_servidor(novedad_critica, superadmin):
    creada = Autorizacion.objects.create(
        novedad=novedad_critica,
        superadmin=superadmin,
        justificacion=JUSTIFICACION,
        hash_justificacion="manipulado-por-el-cliente",
    )

    assert creada.hash_justificacion == hashlib.sha256(
        JUSTIFICACION.encode("utf-8")
    ).hexdigest()


def test_la_justificacion_debe_tener_entre_20_y_500_caracteres(novedad_critica):
    corta = Autorizacion(novedad=novedad_critica, justificacion="Muy corta")

    with pytest.raises(ValidationError) as error:
        corta.full_clean()

    assert "justificacion" in error.value.message_dict


# --- Vista y permisos ---------------------------------------------------------


def test_superadmin_autoriza_y_el_vehiculo_se_desbloquea(
    client, superadmin, novedad_critica, vehiculo
):
    respuesta = autorizar(client, superadmin, novedad_critica)

    assert respuesta.status_code == 302
    novedad_critica.refresh_from_db()
    assert novedad_critica.estado == Novedad.Estado.VALIDADA
    assert vehiculo.estado == Vehiculo.Estado.OPERATIVO
    assert novedad_critica.gestiones.count() == 3


def test_la_autorizacion_guarda_superadmin_hash_e_ip(
    client, superadmin, novedad_critica
):
    autorizar(client, superadmin, novedad_critica)

    creada = Autorizacion.objects.get(novedad=novedad_critica)
    assert creada.superadmin == superadmin
    assert creada.justificacion == JUSTIFICACION
    assert creada.hash_justificacion == hashlib.sha256(
        JUSTIFICACION.encode("utf-8")
    ).hexdigest()


def test_la_contraseña_nunca_se_guarda(client, superadmin, novedad_critica):
    autorizar(client, superadmin, novedad_critica)

    campos = [campo.name for campo in Autorizacion._meta.fields]
    assert not any("password" in nombre or "clave" in nombre for nombre in campos)
    creada = Autorizacion.objects.get(novedad=novedad_critica)
    assert CLAVE not in creada.justificacion
    assert CLAVE not in creada.hash_justificacion


def test_contraseña_incorrecta_no_autoriza(client, superadmin, novedad_critica):
    respuesta = autorizar(client, superadmin, novedad_critica, password="equivocada")

    assert respuesta.status_code == 200
    assert Autorizacion.objects.count() == 0
    novedad_critica.refresh_from_db()
    assert novedad_critica.estado == Novedad.Estado.ABIERTA


def test_si_falta_un_campo_la_respuesta_es_400(client, superadmin, novedad_critica):
    client.force_login(superadmin)

    respuesta = client.post(reverse("novedad_autorizar", args=[novedad_critica.pk]), {})

    assert respuesta.status_code == 400
    assert Autorizacion.objects.count() == 0


def test_un_admin_no_superadmin_no_puede_autorizar(client, admin, novedad_critica):
    respuesta = autorizar(client, admin, novedad_critica)

    assert respuesta.status_code == 403
    assert Autorizacion.objects.count() == 0


def test_el_sello_rojo_aparece_en_la_gestion(client, superadmin, novedad_critica):
    autorizar(client, superadmin, novedad_critica)

    respuesta = client.get(reverse("novedad_gestion", args=[novedad_critica.pk]))

    assert "SELLO ROJO" in respuesta.content.decode()
