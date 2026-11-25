"""Pruebas de los modelos de notificaciones y preferencias."""

from django.utils import timezone

from ..models import (
    Canal,
    Estado,
    Evento,
    Notificacion,
    PreferenciaNotificacion,
    SuscripcionPush,
)
from ..servicios import crear_notificaciones


def test_crear_notificaciones_no_duplica(admin):
    primeras = crear_notificaciones(
        admin, Evento.PRUEBA, "Prueba", "Mensaje", clave="unica"
    )
    segundas = crear_notificaciones(
        admin, Evento.PRUEBA, "Prueba", "Mensaje", clave="unica"
    )

    assert len(primeras) == 4
    assert segundas == []
    assert Notificacion.objects.filter(usuario=admin, clave="unica").count() == 4


def test_preferencia_puede_silenciar_correo_pero_no_un_critico(admin):
    preferencia = PreferenciaNotificacion.objects.create(
        usuario=admin, correo=False, web_push=False
    )

    assert not preferencia.permite(Evento.RESUMEN_DIARIO, Canal.CORREO)
    assert not preferencia.permite(Evento.RESUMEN_DIARIO, Canal.WEB_PUSH)
    assert preferencia.permite(Evento.RESUMEN_DIARIO, Canal.APP)
    assert preferencia.permite(Evento.NOVEDAD_CRITICA, Canal.CORREO)
    assert preferencia.permite(Evento.NOVEDAD_CRITICA, Canal.TELEGRAM)


def test_sin_preferencia_se_usan_valores_por_defecto(admin):
    preferencia = PreferenciaNotificacion.para(admin)

    assert preferencia.pk is None
    assert preferencia.permite(Evento.RESUMEN_DIARIO, Canal.CORREO)
    assert preferencia.permite(Evento.RESUMEN_DIARIO, Canal.WEB_PUSH)


def test_marcar_enviada_y_leida(notificacion):
    notificacion.marcar_enviada()
    notificacion.refresh_from_db()
    assert notificacion.estado == Estado.ENVIADA
    assert notificacion.enviado_en is not None

    notificacion.marcar_leida()
    notificacion.refresh_from_db()
    assert notificacion.estado == Estado.LEIDA
    assert notificacion.sin_leer is False


def test_reintentos_con_espera_creciente(notificacion):
    notificacion.registrar_fallo("SMTP caído", espera_segundos=60)
    notificacion.refresh_from_db()
    assert notificacion.intentos == 1
    assert notificacion.estado == Estado.PENDIENTE
    primera = notificacion.proximo_intento_en

    notificacion.registrar_fallo("SMTP caído", espera_segundos=60)
    notificacion.refresh_from_db()
    assert notificacion.intentos == 2
    assert notificacion.proximo_intento_en > primera

    notificacion.registrar_fallo("SMTP caído", espera_segundos=60)
    notificacion.refresh_from_db()
    assert notificacion.intentos == 3
    assert notificacion.estado == Estado.FALLIDA
    assert notificacion.proximo_intento_en is None
    assert notificacion.error == "SMTP caído"


def test_suscripcion_push_unica_por_endpoint(conductor):
    SuscripcionPush.objects.create(
        usuario=conductor.usuario,
        endpoint="https://push.example.com/abc",
        p256dh="clave-publica",
        auth="clave-auth",
    )
    SuscripcionPush.objects.update_or_create(
        endpoint="https://push.example.com/abc",
        defaults={
            "usuario": conductor.usuario,
            "p256dh": "nueva",
            "auth": "nueva-auth",
            "activa": True,
        },
    )

    suscripcion = SuscripcionPush.objects.get(endpoint="https://push.example.com/abc")
    assert suscripcion.p256dh == "nueva"
    assert SuscripcionPush.objects.count() == 1


def test_es_critica_por_evento_aunque_la_fila_diga_lo_contrario(admin):
    notificacion = Notificacion.objects.create(
        usuario=admin,
        evento=Evento.SOLICITUD_AUTORIZACION,
        canal=Canal.APP,
        titulo="Firma",
        mensaje="Firma requerida",
        creado_en=timezone.now(),
    )
    assert notificacion.es_critica is True
