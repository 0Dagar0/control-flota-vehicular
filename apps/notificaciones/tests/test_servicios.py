"""Pruebas de las reglas de negocio: destinatarios, eventos y resumen."""

from datetime import timedelta

from django.utils import timezone

from apps.flota.models import (
    Documento,
    Inspeccion,
    Mantenimiento,
    Novedad,
    PlantillaInspeccion,
    Servicio,
)

from ..models import Canal, Estado, Evento, Notificacion
from ..servicios import (
    crear_notificaciones,
    datos_resumen,
    escalar,
    generar_resumen_diario,
    notificar_autorizacion,
    notificar_novedad,
    notificar_servicio_con_novedad,
    pendientes_de_escalamiento,
    texto_resumen,
    verificar_inspecciones_pendientes,
)


def test_novedad_critica_avisa_a_admin_y_superadmin_por_cuatro_canales(
    admin, superadmin, vehiculo
):
    novedad = Novedad.objects.create(
        vehiculo=vehiculo,
        descripcion="Fuga de aceite en el motor",
        severidad=Novedad.Severidad.CRITICA,
    )

    creadas = notificar_novedad(novedad)

    criticas = Notificacion.objects.filter(evento=Evento.NOVEDAD_CRITICA)
    firmas = Notificacion.objects.filter(evento=Evento.SOLICITUD_AUTORIZACION)
    assert criticas.count() == 8  # 2 usuarios × 4 canales
    assert firmas.count() == 4  # solo superadministradores
    assert set(criticas.values_list("canal", flat=True)) == set(Canal.values)
    assert all(item.es_critica for item in Notificacion.objects.all())
    assert len(creadas) == 12


def test_novedad_no_critica_no_genera_avisos(admin, superadmin, vehiculo):
    novedad = Novedad.objects.create(
        vehiculo=vehiculo,
        descripcion="Ruido leve en la puerta",
        severidad=Novedad.Severidad.MEDIA,
    )
    assert notificar_novedad(novedad) == []
    assert Notificacion.objects.count() == 0


def test_autorizacion_avisa_al_conductor_y_admin(admin, conductor, vehiculo):
    novedad = Novedad.objects.create(
        vehiculo=vehiculo,
        conductor=conductor,
        descripcion="Falla de frenos",
        severidad=Novedad.Severidad.CRITICA,
    )
    Notificacion.objects.all().delete()

    notificar_autorizacion(novedad)

    filas = Notificacion.objects.filter(evento=Evento.AUTORIZACION_CONCEDIDA)
    assert filas.count() == 4
    assert set(filas.values_list("usuario", flat=True)) == {
        admin.pk,
        conductor.usuario.pk,
    }
    assert set(filas.values_list("canal", flat=True)) == {Canal.APP, Canal.CORREO}


def test_resumen_diario_incluye_documentos_y_mantenimientos(admin, vehiculo):
    Documento.objects.create(
        tipo=Documento.Tipo.SOAT,
        entidad="Aseguradora",
        numero="SOAT-1",
        vehiculo=vehiculo,
        vencimiento=timezone.localdate() + timedelta(days=3),
    )
    Mantenimiento.objects.create(
        vehiculo=vehiculo,
        servicio="Cambio de aceite",
        parte="Motor",
        km=80_000,
        proximo_km=84_700,  # faltan 400 km, bajo el umbral de 500
    )

    creadas = generar_resumen_diario()

    assert len(creadas) == 2  # app y correo para el administrador
    mensaje = creadas[0].mensaje
    assert "3 día(s)" in mensaje
    assert "faltan 400 km" in mensaje
    assert "documentos" in texto_resumen(datos_resumen()).lower()


def test_escalamiento_repite_critica_por_cuatro_canales(admin):
    crear_notificaciones(
        admin,
        Evento.NOVEDAD_CRITICA,
        "Novedad crítica en ABC123",
        "Motor humeando",
        clave="novedad:9",
    )
    Notificacion.objects.filter(usuario=admin).update(
        estado=Estado.ENVIADA,
        enviado_en=timezone.now() - timedelta(minutes=10),
        creado_en=timezone.now() - timedelta(minutes=10),
    )
    original = Notificacion.objects.filter(usuario=admin).first()

    vencidas = list(pendientes_de_escalamiento(5))
    repetidas = []
    for critica in vencidas:
        repetidas += escalar(critica)

    assert len(vencidas) == 4
    assert len(repetidas) == 16  # 4 canales originales × 4 canales de repetición
    assert all(item.clave.startswith("escala:") for item in repetidas)
    original.refresh_from_db()
    assert original.escalada_en is not None
    assert pendientes_de_escalamiento(5).count() == 0


def test_servicio_cerrado_con_novedad_avisa_al_admin(admin, conductor, vehiculo):
    servicio = Servicio.objects.create(
        vehiculo=vehiculo,
        conductor=conductor,
        km_inicial=84_300,
        ruta="Ruta norte",
        sin_novedad=False,
        observacion_cierre="Llanta ponchada en el km 84.310",
    )

    creadas = notificar_servicio_con_novedad(servicio)

    assert len(creadas) == 1
    assert creadas[0].evento == Evento.SERVICIO_CON_NOVEDAD
    assert creadas[0].canal == Canal.APP
    assert "Llanta ponchada" in creadas[0].mensaje
    assert notificar_servicio_con_novedad(servicio) == []


def test_inspeccion_pendiente_al_mediodia(admin, conductor, vehiculo):
    plantilla = PlantillaInspeccion.objects.create(nombre="Rápida")
    inspeccion = Inspeccion.objects.create(
        vehiculo=vehiculo,
        conductor=conductor,
        plantilla=plantilla,
        km=84_300,
    )
    Inspeccion.objects.filter(pk=inspeccion.pk).update(
        iniciado_en=timezone.now() - timedelta(hours=6)
    )

    creadas = verificar_inspecciones_pendientes()

    assert len(creadas) == 1
    assert creadas[0].evento == Evento.INSPECCION_PENDIENTE
    assert creadas[0].canal == Canal.APP
    assert verificar_inspecciones_pendientes() == []
