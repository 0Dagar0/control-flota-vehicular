"""Pruebas de los modelos de la flota y de las reglas R11, R12, R19, R20 y R21."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.flota.models import Conductor, Configuracion, Documento, Vehiculo
from apps.usuarios.models import Usuario


@pytest.fixture
def usuario_conductor(db):
    return Usuario.objects.create_user(
        documento="10203040",
        email="conductor@ejemplo.com",
        password="ClaveSegura2026",
        first_name="Carlos",
        last_name="Pérez",
        rol=Usuario.Rol.CONDUCTOR,
    )


@pytest.fixture
def conductor(db, usuario_conductor):
    return Conductor.objects.create(
        usuario=usuario_conductor,
        licencia_categoria=Conductor.CategoriaLicencia.C2,
        licencia_vencimiento=timezone.localdate() + timedelta(days=365),
        contacto_emergencia_nombre="María Pérez",
        contacto_emergencia_telefono="3001234567",
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


def documento(vehiculo=None, conductor=None, **cambios):
    datos = {
        "tipo": Documento.Tipo.SOAT if vehiculo else Documento.Tipo.LICENCIA,
        "vehiculo": vehiculo,
        "conductor": conductor,
        "entidad": "Aseguradora de prueba",
        "numero": "SOAT-001",
        "vencimiento": timezone.localdate() + timedelta(days=12),
        "soporte": "documentos/2026/11/soporte.pdf",
    }
    datos.update(cambios)
    return Documento(**datos)


# --- Configuración -----------------------------------------------------------


@pytest.mark.django_db
def test_configuracion_es_un_singleton():
    primera = Configuracion.obtener()
    segunda = Configuracion.obtener()

    assert primera.pk == 1
    assert segunda.pk == 1
    assert Configuracion.objects.count() == 1
    assert primera.umbral_mantenimiento_km == 500
    assert primera.minutos_autorizacion == 15


@pytest.mark.django_db
def test_configuracion_siempre_guarda_la_clave_1():
    Configuracion.objects.create(pk=5, umbral_mantenimiento_km=800)

    assert Configuracion.objects.count() == 1
    assert Configuracion.obtener().umbral_mantenimiento_km == 800


# --- Vehículo ----------------------------------------------------------------


@pytest.mark.django_db
def test_vehiculo_sin_documentos_es_operativo(vehiculo):
    assert vehiculo.estado == Vehiculo.Estado.OPERATIVO


@pytest.mark.django_db
def test_documento_vencido_bloquea_el_vehiculo(vehiculo):
    vencido = documento(vehiculo=vehiculo, vencimiento=timezone.localdate() - timedelta(days=1))
    vencido.save()

    assert vehiculo.documentos_vencidos.count() == 1
    assert vehiculo.estado == Vehiculo.Estado.BLOQUEADO_DOCUMENTO


@pytest.mark.django_db
def test_vehiculo_inactivo_queda_fuera_de_servicio(vehiculo):
    vehiculo.activo = False
    vehiculo.save()

    assert vehiculo.estado == Vehiculo.Estado.FUERA_DE_SERVICIO


@pytest.mark.django_db
def test_el_kilometraje_no_puede_disminuir(vehiculo):
    vehiculo.km_actual = 84_000

    with pytest.raises(ValidationError) as error:
        vehiculo.full_clean()

    assert "km_actual" in error.value.message_dict


@pytest.mark.django_db
def test_la_placa_se_guarda_en_mayusculas():
    vehiculo = Vehiculo.objects.create(
        placa="def456", marca="Chevrolet", referencia="NHR", modelo=2022
    )

    assert vehiculo.placa == "DEF456"


@pytest.mark.django_db
def test_placa_con_formato_invalido_no_pasa_la_validacion():
    vehiculo = Vehiculo(placa="ABC12", marca="Renault", referencia="Kangoo", modelo=2020)

    with pytest.raises(ValidationError) as error:
        vehiculo.full_clean()

    assert "placa" in error.value.message_dict


@pytest.mark.django_db
def test_modelo_fuera_de_rango_no_pasa_la_validacion():
    vehiculo = Vehiculo(placa="GHI789", marca="Renault", referencia="Kangoo", modelo=1900)

    with pytest.raises(ValidationError) as error:
        vehiculo.full_clean()

    assert "modelo" in error.value.message_dict


# --- Conductor ---------------------------------------------------------------


@pytest.mark.django_db
def test_conductor_con_licencia_vigente_esta_activo(conductor):
    assert conductor.licencia_vigente is True
    assert conductor.estado == Conductor.Estado.ACTIVO


@pytest.mark.django_db
def test_licencia_vencida_inhabilita_al_conductor_no_al_vehiculo(conductor, vehiculo):
    conductor.licencia_vencimiento = timezone.localdate() - timedelta(days=1)
    conductor.save()

    assert conductor.estado == Conductor.Estado.NO_HABILITADO
    assert vehiculo.estado == Vehiculo.Estado.OPERATIVO


@pytest.mark.django_db
def test_baja_sin_fecha_es_invalida(conductor):
    conductor.activo = False

    with pytest.raises(ValidationError) as error:
        conductor.full_clean()

    assert "fecha_baja" in error.value.message_dict


@pytest.mark.django_db
def test_baja_con_fecha_y_motivo_deja_al_conductor_inactivo(conductor):
    conductor.activo = False
    conductor.fecha_baja = timezone.localdate()
    conductor.motivo_baja = "Renuncia voluntaria"
    conductor.full_clean()
    conductor.save()

    assert conductor.estado == Conductor.Estado.INACTIVO


@pytest.mark.django_db
def test_un_conductor_activo_no_puede_tener_fecha_de_baja(conductor):
    conductor.fecha_baja = timezone.localdate()

    with pytest.raises(ValidationError) as error:
        conductor.full_clean()

    assert "fecha_baja" in error.value.message_dict


# --- Documento ---------------------------------------------------------------


@pytest.mark.django_db
def test_documento_sin_soporte_queda_pendiente_pero_se_guarda(vehiculo):
    """R19 (actualizada): el soporte puede subirse después; se marca pendiente."""
    sin_soporte = documento(vehiculo=vehiculo, soporte="")
    sin_soporte.full_clean()

    assert sin_soporte.tiene_soporte is False
    assert sin_soporte.estado_soporte == "Pendiente"


@pytest.mark.django_db
def test_documento_con_soporte_se_marca_cargado(vehiculo):
    con_soporte = documento(vehiculo=vehiculo)
    con_soporte.full_clean()

    assert con_soporte.tiene_soporte is True
    assert con_soporte.estado_soporte == "Cargado"


@pytest.mark.django_db
def test_licencia_debe_pertenecer_al_conductor(vehiculo):
    licencia = documento(vehiculo=vehiculo, tipo=Documento.Tipo.LICENCIA)

    with pytest.raises(ValidationError) as error:
        licencia.full_clean()

    assert "conductor" in error.value.message_dict


@pytest.mark.django_db
def test_soat_debe_pertenecer_al_vehiculo(conductor):
    soat = documento(conductor=conductor, tipo=Documento.Tipo.SOAT)

    with pytest.raises(ValidationError) as error:
        soat.full_clean()

    assert "vehiculo" in error.value.message_dict


@pytest.mark.django_db
def test_documento_sin_dueno_no_es_valido():
    huerfano = documento()

    with pytest.raises(ValidationError):
        huerfano.full_clean()


@pytest.mark.django_db
def test_documento_con_dos_duenos_no_es_valido(vehiculo, conductor):
    doble = documento(vehiculo=vehiculo, conductor=conductor)

    with pytest.raises(ValidationError):
        doble.full_clean()


@pytest.mark.django_db
def test_estado_del_documento_segun_los_dias(vehiculo):
    vigente = documento(vehiculo=vehiculo, vencimiento=timezone.localdate() + timedelta(days=60))
    por_vencer = documento(vehiculo=vehiculo, vencimiento=timezone.localdate() + timedelta(days=10))
    vencido = documento(vehiculo=vehiculo, vencimiento=timezone.localdate() - timedelta(days=1))

    assert vigente.estado == "Vigente"
    assert por_vencer.estado == "Por vencer"
    assert vencido.estado == "Vencido"
    assert vehiculo.documentos_vencidos.count() == 0  # aún sin guardar
