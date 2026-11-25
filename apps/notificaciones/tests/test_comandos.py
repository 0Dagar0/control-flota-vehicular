"""Pruebas de los comandos de comprobación y de la cola de envíos."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from .. import enviadores
from ..management.commands import comprobar_telegram as cmd_telegram
from ..management.commands import enviar_notificaciones as cmd_cola
from ..models import Estado, Evento, Notificacion
from ..servicios import crear_notificaciones

TOKEN_FALSO = "123456789:AAtokenFalsoParaPruebas1234567890abc"


@pytest.fixture
def telegram_falso(monkeypatch, settings):
    settings.TELEGRAM_BOT_TOKEN = TOKEN_FALSO
    enviados = []

    def falso(token, metodo, datos=None, post=False):
        if metodo == "getMe":
            return {
                "ok": True,
                "result": {
                    "id": 9206039737,
                    "username": "MiFlotaGranjeroBot",
                    "first_name": "MiFlotaGranjeroBot",
                },
            }
        if metodo == "getUpdates":
            return {
                "ok": True,
                "result": [
                    {
                        "update_id": 1,
                        "message": {
                            "chat": {
                                "id": 111222333,
                                "type": "private",
                                "first_name": "William",
                            }
                        },
                    }
                ],
            }
        enviados.append(datos)
        return {"ok": True, "result": {"message_id": 3}}

    monkeypatch.setattr(cmd_telegram, "telegram_api", falso)
    return enviados


def test_comprobar_telegram_muestra_bot_y_envia_a_chat(telegram_falso):
    salida = StringIO()

    call_command("comprobar_telegram", stdout=salida)

    texto = salida.getvalue()
    assert "@MiFlotaGranjeroBot" in texto
    assert "chat_id=111222333" in texto
    assert TOKEN_FALSO not in texto
    assert telegram_falso[0]["chat_id"] == "111222333"


def test_comprobar_telegram_sin_envio_no_escribe(telegram_falso):
    salida = StringIO()

    call_command("comprobar_telegram", "--sin-envio", stdout=salida)

    assert "@MiFlotaGranjeroBot" in salida.getvalue()
    assert telegram_falso == []


def test_comprobar_telegram_rechaza_marcador(settings):
    settings.TELEGRAM_BOT_TOKEN = "<PEGA_AQUI_EL_TOKEN_DE_BOTFATHER>"

    with pytest.raises(CommandError, match="TELEGRAM_BOT_TOKEN"):
        call_command("comprobar_telegram", stdout=StringIO())


def test_cola_marca_enviada(notificacion, monkeypatch):
    monkeypatch.setattr(cmd_cola, "enviar", lambda notificacion: None)

    salida = StringIO()
    call_command("enviar_notificaciones", "--espera", "0", stdout=salida)

    notificacion.refresh_from_db()
    assert notificacion.estado == Estado.ENVIADA
    assert notificacion.enviado_en is not None
    assert "1 enviada" in salida.getvalue()


def test_cola_registra_tres_fallos(notificacion, monkeypatch):
    def falla(notificacion):
        raise enviadores.ErrorEnvio("SMTP caído")

    monkeypatch.setattr(cmd_cola, "enviar", falla)
    opciones = ("--espera", "0", "--intentos", "3")

    for _ in range(3):
        call_command("enviar_notificaciones", *opciones, stdout=StringIO())

    notificacion.refresh_from_db()
    assert notificacion.intentos == 3
    assert notificacion.estado == Estado.FALLIDA
    assert notificacion.error == "SMTP caído"


def test_cola_escala_critica_sin_abrir(admin, monkeypatch):
    monkeypatch.setattr(cmd_cola, "enviar", lambda notificacion: None)
    crear_notificaciones(
        admin,
        Evento.NOVEDAD_CRITICA,
        "Novedad crítica en ABC123",
        "Motor humeando",
        clave="novedad:5",
    )
    Notificacion.objects.filter(usuario=admin).update(
        estado=Estado.ENVIADA,
        creado_en=timezone.now() - timedelta(minutes=10),
    )

    call_command(
        "enviar_notificaciones", "--espera", "0", "--escalar-minutos", "5", stdout=StringIO()
    )

    assert Notificacion.objects.filter(clave__startswith="escala:").count() == 16


def test_cola_con_resumen_genera_aviso(admin, monkeypatch):
    monkeypatch.setattr(cmd_cola, "enviar", lambda notificacion: None)

    call_command(
        "enviar_notificaciones", "--resumen", "--espera", "0", stdout=StringIO()
    )

    assert Notificacion.objects.filter(evento=Evento.RESUMEN_DIARIO).count() == 2


def test_cola_con_mediodia_genera_aviso_de_inspeccion(admin, monkeypatch):
    monkeypatch.setattr(cmd_cola, "enviar", lambda notificacion: None)
    monkeypatch.setattr(
        cmd_cola,
        "verificar_inspecciones_pendientes",
        lambda: [object()],
    )

    salida = StringIO()
    call_command("enviar_notificaciones", "--mediodia", stdout=salida)

    assert "1 aviso(s) nuevo(s)" in salida.getvalue()
