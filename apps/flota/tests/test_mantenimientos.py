"""Pruebas de mantenimientos e incidentes (v1.1, contrato §5.4 y R16/R17)."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.flota.models import (
    Conductor,
    Incidente,
    Mantenimiento,
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


def mantenimiento(vehiculo, **cambios):
    datos = {
        "vehiculo": vehiculo,
        "tipo": Mantenimiento.Tipo.PREVENTIVO,
        "servicio": "Cambio de aceite",
        "parte": "Motor",
        "fecha": timezone.localdate(),
        "km": vehiculo.km_actual,
        "proximo_km": vehiculo.km_actual + 1_000,
    }
    datos.update(cambios)
    return Mantenimiento(**datos)


# --- Reglas del modelo --------------------------------------------------------


def test_el_proximo_km_debe_ser_mayor(vehiculo):
    invalido = mantenimiento(vehiculo, proximo_km=vehiculo.km_actual)

    with pytest.raises(ValidationError) as error:
        invalido.full_clean()

    assert "proximo_km" in error.value.message_dict


def test_la_fecha_no_puede_ser_futura(vehiculo):
    invalido = mantenimiento(
        vehiculo, fecha=timezone.localdate() + timedelta(days=1)
    )

    with pytest.raises(ValidationError) as error:
        invalido.full_clean()

    assert "fecha" in error.value.message_dict


def test_el_km_no_puede_bajar_del_registrado(vehiculo):
    invalido = mantenimiento(vehiculo, km=vehiculo.km_actual - 100)

    with pytest.raises(ValidationError) as error:
        invalido.full_clean()

    assert "km" in error.value.message_dict


def test_semforo_por_distancia(vehiculo):
    cercano = mantenimiento(vehiculo, proximo_km=vehiculo.km_actual + 100)
    cercano.save()
    lejano = mantenimiento(vehiculo, proximo_km=vehiculo.km_actual + 1_000)
    lejano.save()

    assert cercano.estado_semforo == "aviso"
    assert "Faltan 100 km" in cercano.mensaje_km
    assert lejano.estado_semforo == "ok"

    vehiculo.km_actual = vehiculo.km_actual + 200
    vehiculo.save()
    assert cercano.estado_semforo == "vencido"


def test_la_factura_pasa_o_no_segun_extension(vehiculo):
    valida = mantenimiento(
        vehiculo,
        soporte_factura=SimpleUploadedFile("factura.pdf", b"%PDF-1.4 prueba"),
    )
    valida.full_clean()
    valida.save()
    assert valida.estado_factura == Mantenimiento.EstadoFactura.ADJUNTA

    invalida = mantenimiento(
        vehiculo,
        soporte_factura=SimpleUploadedFile("mal.exe", b"no soy factura"),
    )
    with pytest.raises(ValidationError):
        invalida.full_clean()


# --- Vistas -------------------------------------------------------------------


def test_admin_registra_un_mantenimiento(client, admin, vehiculo):
    client.force_login(admin)

    respuesta = client.post(
        reverse("mantenimiento_nuevo"),
        {
            "vehiculo": vehiculo.pk,
            "tipo": "preventivo",
            "servicio": "Cambio de aceite",
            "parte": "Motor",
            "fecha": timezone.localdate().isoformat(),
            "km": vehiculo.km_actual,
            "proximo_km": vehiculo.km_actual + 1_000,
        },
    )

    assert respuesta.status_code == 302
    creado = Mantenimiento.objects.get(vehiculo=vehiculo)
    assert creado.creado_por == admin
    assert creado.estado_factura == Mantenimiento.EstadoFactura.PENDIENTE


def test_la_vista_rechaza_un_proximo_km_invalido(client, admin, vehiculo):
    client.force_login(admin)

    respuesta = client.post(
        reverse("mantenimiento_nuevo"),
        {
            "vehiculo": vehiculo.pk,
            "tipo": "preventivo",
            "servicio": "Cambio de aceite",
            "parte": "Motor",
            "fecha": timezone.localdate().isoformat(),
            "km": vehiculo.km_actual,
            "proximo_km": vehiculo.km_actual,
        },
    )

    assert respuesta.status_code == 200
    assert Mantenimiento.objects.count() == 0


def test_el_listado_muestra_el_aviso(client, admin, vehiculo):
    mantenimiento(vehiculo, proximo_km=vehiculo.km_actual + 100).save()
    client.force_login(admin)

    respuesta = client.get(reverse("mantenimientos"))

    assert respuesta.status_code == 200
    assert "Faltan 100 km" in respuesta.content.decode()


def test_admin_registra_un_incidente(client, admin, vehiculo, conductor):
    client.force_login(admin)

    respuesta = client.post(
        reverse("incidente_nuevo"),
        {
            "vehiculo": vehiculo.pk,
            "conductor": conductor.pk,
            "fecha": timezone.localdate().isoformat(),
            "gravedad": "leve",
            "descripcion": "Rasguño en la puerta lateral",
            "causa": "Aparcamiento ajustado",
            "accion": "Se documentó y se avisó al administrador",
        },
    )

    assert respuesta.status_code == 302
    creado = Incidente.objects.get(vehiculo=vehiculo)
    assert creado.creado_por == admin
    assert creado.gravedad == Incidente.Gravedad.LEVE


def test_la_vista_360_muestra_mantenimientos_e_incidentes(
    client, admin, vehiculo, conductor
):
    mantenimiento(vehiculo).save()
    Incidente.objects.create(
        vehiculo=vehiculo, conductor=conductor, descripcion="Cristal roto"
    )
    client.force_login(admin)

    respuesta = client.get(reverse("hoja_vida_360", args=["ABC123"]))

    contenido = respuesta.content.decode()
    assert "Cambio de aceite" in contenido
    assert "Cristal roto" in contenido
