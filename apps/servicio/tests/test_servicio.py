"""Pruebas de la asignación de vehículo y del servicio del conductor (v0.5)."""

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
        documento="800200200",
        email="admin@ejemplo.com",
        password=CLAVE,
        first_name="Ana",
        last_name="Rojas",
        rol=Usuario.Rol.ADMIN,
    )


@pytest.fixture
def conductor(db):
    """Conductor activo con licencia vigente y usuario para entrar al sistema."""
    usuario = Usuario.objects.create_user(
        documento="10203040",
        email="carlos@ejemplo.com",
        password=CLAVE,
        first_name="Carlos",
        last_name="Pérez",
    )
    return Conductor.objects.create(
        usuario=usuario,
        licencia_categoria="c2",
        licencia_vencimiento=timezone.localdate() + timedelta(days=365),
    )


@pytest.fixture
def vehiculo(db):
    return Vehiculo.objects.create(
        placa="ABC123",
        marca="FOTON",
        referencia="BJ1044",
        modelo=2025,
        km_actual=1000,
    )


@pytest.fixture
def asignacion(vehiculo, conductor):
    return Asignacion.objects.create(vehiculo=vehiculo, conductor=conductor)


def documento_vigente(vehiculo):
    return Documento.objects.create(
        tipo=Documento.Tipo.SOAT,
        vehiculo=vehiculo,
        vencimiento=timezone.localdate() + timedelta(days=200),
    )


def iniciar(client, conductor, **datos):
    client.force_login(conductor.usuario)
    return client.post(
        reverse("servicio:iniciar"),
        {"km_inicial": 1200, "ruta": "Ruta norte: bodega → Soacha", **datos},
    )


def url_cerrar(conductor):
    """URL del servicio abierto del conductor (la ruta lleva su id)."""
    servicio = Servicio.objects.get(conductor=conductor, cerrado_en__isnull=True)
    return reverse("servicio:cerrar", args=[servicio.pk])


# ---------------------------------------------------------------------------
# Asignación de vehículo (solo admin y superadmin)
# ---------------------------------------------------------------------------
def test_el_admin_asigna_vehiculo_al_conductor(client, admin, conductor, vehiculo):
    client.force_login(admin)
    respuesta = client.post(
        reverse("maestros:conductor_asignar", args=[conductor.pk]),
        {"vehiculo": vehiculo.pk, "fecha_inicio": timezone.localdate().isoformat()},
    )

    assert respuesta.status_code == 302
    asignacion = Asignacion.objects.get(conductor=conductor)
    assert asignacion.vehiculo == vehiculo
    assert asignacion.activa is True
    assert asignacion.creado_por == admin
    assert conductor.vehiculo_actual == vehiculo


def test_el_conductor_no_puede_asignarse_vehiculo(client, conductor, vehiculo):
    """El conductor no se asigna nada: la vista lo saca de la sección de flota."""
    client.force_login(conductor.usuario)
    respuesta = client.post(
        reverse("maestros:conductor_asignar", args=[conductor.pk]),
        {"vehiculo": vehiculo.pk, "fecha_inicio": timezone.localdate().isoformat()},
    )

    assert respuesta.status_code == 403
    assert Asignacion.objects.count() == 0


def test_cambiar_de_vehiculo_cierra_la_asignacion_anterior(client, admin, conductor, vehiculo, db):
    """R18: el historial no se borra; la asignación anterior queda cerrada."""
    otro = Vehiculo.objects.create(
        placa="XYZ789", marca="CHEVROLET", referencia="NHR", modelo=2018, km_actual=500
    )
    Asignacion.objects.create(vehiculo=vehiculo, conductor=conductor)
    client.force_login(admin)

    respuesta = client.post(
        reverse("maestros:conductor_asignar", args=[conductor.pk]),
        {
            "vehiculo": otro.pk,
            "fecha_inicio": timezone.localdate().isoformat(),
            "motivo": "Cambio de ruta",
        },
    )

    assert respuesta.status_code == 302
    assert Asignacion.objects.filter(conductor=conductor).count() == 2
    anterior = Asignacion.objects.get(conductor=conductor, vehiculo=vehiculo)
    assert anterior.fecha_fin == timezone.localdate()
    assert anterior.motivo_fin == "Cambio de ruta"
    assert conductor.vehiculo_actual == otro


def test_un_conductor_dado_de_baja_no_recibe_vehiculo(
    client, admin, conductor, vehiculo
):
    client.force_login(admin)
    conductor.activo = False
    conductor.fecha_baja = timezone.localdate()
    conductor.motivo_baja = "Renuncia"
    conductor.save()
    respuesta = client.post(
        reverse("maestros:conductor_asignar", args=[conductor.pk]),
        {"vehiculo": vehiculo.pk, "fecha_inicio": timezone.localdate().isoformat()},
    )

    assert respuesta.status_code == 302
    assert Asignacion.objects.count() == 0


def test_un_vehiculo_no_puede_tener_dos_asignaciones_activas(
    client, admin, conductor, vehiculo
):
    otro_usuario = Usuario.objects.create_user(
        documento="50607080", email="otro@ejemplo.com", password=CLAVE
    )
    otro_conductor = Conductor.objects.create(
        usuario=otro_usuario,
        licencia_categoria="c2",
        licencia_vencimiento=timezone.localdate() + timedelta(days=365),
    )
    Asignacion.objects.create(vehiculo=vehiculo, conductor=conductor)
    client.force_login(admin)

    respuesta = client.post(
        reverse("maestros:conductor_asignar", args=[otro_conductor.pk]),
        {"vehiculo": vehiculo.pk, "fecha_inicio": timezone.localdate().isoformat()},
    )

    assert respuesta.status_code == 200
    assert Asignacion.objects.filter(vehiculo=vehiculo, fecha_fin__isnull=True).count() == 1


# ---------------------------------------------------------------------------
# Iniciar servicio
# ---------------------------------------------------------------------------
def test_sin_vehiculo_asignado_no_se_puede_iniciar(client, conductor):
    respuesta = iniciar(client, conductor)

    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("mi_servicio")
    assert Servicio.objects.count() == 0


def test_iniciar_servicio_guarda_km_y_ruta(client, conductor, asignacion):
    respuesta = iniciar(client, conductor)

    assert respuesta.status_code == 302
    servicio = Servicio.objects.get(conductor=conductor)
    assert servicio.km_inicial == 1200
    assert servicio.ruta.startswith("Ruta norte")
    assert servicio.cerrado_en is None
    asignacion.vehiculo.refresh_from_db()
    assert asignacion.vehiculo.km_actual == 1200


def test_el_km_inicial_no_puede_ser_menor_al_del_vehiculo(client, conductor, asignacion):
    """R12: el kilometraje nunca disminuye."""
    respuesta = iniciar(client, conductor, km_inicial=900)

    assert respuesta.status_code == 200
    assert "no puede ser menor" in respuesta.content.decode()
    assert Servicio.objects.count() == 0


def test_no_se_inicia_con_documento_vencido(client, conductor, asignacion):
    """R11: un documento vencido bloquea la salida."""
    Documento.objects.create(
        tipo=Documento.Tipo.SOAT,
        vehiculo=asignacion.vehiculo,
        vencimiento=timezone.localdate() - timedelta(days=1),
    )

    respuesta = iniciar(client, conductor)

    assert respuesta.status_code == 302
    assert Servicio.objects.count() == 0


def test_no_se_inicia_con_licencia_vencida(client, conductor, asignacion):
    """R21: sin licencia vigente no hay servicio."""
    conductor.licencia_vencimiento = timezone.localdate() - timedelta(days=1)
    conductor.save()

    respuesta = iniciar(client, conductor)

    assert respuesta.status_code == 302
    assert Servicio.objects.count() == 0


def test_no_se_pueden_tener_dos_servicios_en_curso(client, conductor, asignacion):
    iniciar(client, conductor)
    respuesta = iniciar(client, conductor)

    assert respuesta.status_code == 302
    assert Servicio.objects.filter(conductor=conductor).count() == 1


def test_el_conductor_entra_a_mi_servicio(client, conductor, asignacion):
    client.force_login(conductor.usuario)
    respuesta = client.get(reverse("mi_servicio"))

    assert respuesta.status_code == 200
    assert "ABC123" in respuesta.content.decode()


def test_el_conductor_que_inicia_sesion_cae_en_su_pantalla(client, conductor):
    respuesta = client.post(
        reverse("login"),
        {"username": "10203040", "password": CLAVE},
        follow=True,
    )

    assert respuesta.redirect_chain[-1][0] == reverse("mi_servicio")
    assert respuesta.status_code == 200


def test_no_se_puede_cerrar_el_servicio_de_otro_conductor(client, conductor, asignacion, db):
    iniciar(client, conductor)
    servicio = Servicio.objects.get(conductor=conductor)

    otro_usuario = Usuario.objects.create_user(
        documento="50607080", email="otro@ejemplo.com", password=CLAVE
    )
    Conductor.objects.create(
        usuario=otro_usuario,
        licencia_categoria="c2",
        licencia_vencimiento=timezone.localdate() + timedelta(days=365),
    )
    client.force_login(otro_usuario)

    respuesta = client.post(
        reverse("servicio:cerrar", args=[servicio.pk]),
        {"km_final": 1300, "sin_novedad": "on"},
    )

    assert respuesta.status_code == 404
    servicio.refresh_from_db()
    assert servicio.cerrado_en is None


def test_el_administrador_no_entra_a_mi_servicio(client, admin):
    client.force_login(admin)
    respuesta = client.get(reverse("mi_servicio"))

    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("inicio")


# ---------------------------------------------------------------------------
# Cerrar servicio
# ---------------------------------------------------------------------------
def test_cerrar_sin_novedad_actualiza_km_y_servicio(client, conductor, asignacion):
    iniciar(client, conductor)
    documento_vigente(asignacion.vehiculo)
    client.force_login(conductor.usuario)

    respuesta = client.post(
        url_cerrar(conductor), {"km_final": 1350, "sin_novedad": "on"}
    )

    assert respuesta.status_code == 302
    servicio = Servicio.objects.get(conductor=conductor)
    assert servicio.cerrado_en is not None
    assert servicio.sin_novedad is True
    assert servicio.km_recorridos == 150
    asignacion.vehiculo.refresh_from_db()
    assert asignacion.vehiculo.km_actual == 1350


def test_el_km_final_no_puede_ser_menor_al_inicial(client, conductor, asignacion):
    iniciar(client, conductor)
    client.force_login(conductor.usuario)

    respuesta = client.post(
        url_cerrar(conductor), {"km_final": 1100, "sin_novedad": "on"}
    )

    assert respuesta.status_code == 200
    assert "no puede ser menor" in respuesta.content.decode()
    servicio = Servicio.objects.get(conductor=conductor)
    assert servicio.cerrado_en is None


def test_cerrar_con_novedad_exige_descripcion(client, conductor, asignacion):
    iniciar(client, conductor)
    client.force_login(conductor.usuario)

    respuesta = client.post(url_cerrar(conductor), {"km_final": 1350})

    assert respuesta.status_code == 200
    assert "describe qué pasó" in respuesta.content.decode().lower()
    assert Servicio.objects.get(conductor=conductor).cerrado_en is None


def test_cerrar_con_novedad_guarda_la_observacion(client, conductor, asignacion):
    iniciar(client, conductor)
    client.force_login(conductor.usuario)

    respuesta = client.post(
        url_cerrar(conductor),
        {"km_final": 1400, "observacion_cierre": "Falla en la luz derecha"},
    )

    assert respuesta.status_code == 302
    servicio = Servicio.objects.get(conductor=conductor)
    assert servicio.sin_novedad is False
    assert servicio.observacion_cierre == "Falla en la luz derecha"


def test_el_servicio_se_puede_cerrar_aunque_el_vehiculo_quede_bloqueado(
    client, conductor, asignacion
):
    """El cierre siempre se permite: el bloqueo solo impide iniciar."""
    iniciar(client, conductor)
    Documento.objects.create(
        tipo=Documento.Tipo.TECNOMECANICA,
        vehiculo=asignacion.vehiculo,
        vencimiento=timezone.localdate() - timedelta(days=1),
    )
    client.force_login(conductor.usuario)

    respuesta = client.post(
        url_cerrar(conductor), {"km_final": 1250, "sin_novedad": "on"}
    )

    assert respuesta.status_code == 302
    assert Servicio.objects.get(conductor=conductor).cerrado_en is not None


