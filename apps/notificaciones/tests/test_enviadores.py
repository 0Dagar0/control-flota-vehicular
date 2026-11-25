"""Pruebas de los enviadores: nunca salen mensajes reales a Internet."""

import base64
from types import SimpleNamespace

import pytest
import pywebpush
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core import mail

from .. import enviadores
from ..models import Canal


@pytest.fixture
def token_falso(settings):
    settings.TELEGRAM_BOT_TOKEN = "123456789:AAtokenFalsoParaPruebas1234567890abc"
    settings.TELEGRAM_TIMEOUT = 1


@pytest.fixture
def api_falsa(monkeypatch):
    llamadas = []

    def falso(token, metodo, datos=None, post=False):
        llamadas.append((token, metodo, datos, post))
        return {"ok": True, "result": {"message_id": 7}}

    monkeypatch.setattr(enviadores, "telegram_api", falso)
    return llamadas


def test_telegram_envia_al_chat_del_usuario(notificacion, conductor, token_falso, api_falsa):
    notificacion.usuario = conductor.usuario
    notificacion.canal = Canal.TELEGRAM

    enviadores.enviar_telegram(notificacion)

    token, metodo, datos, post = api_falsa[0]
    assert metodo == "sendMessage" and post is True
    assert datos["chat_id"] == "111222333"
    assert "Novedad crítica" in datos["text"]
    assert token == "123456789:AAtokenFalsoParaPruebas1234567890abc"


def test_telegram_sin_token_falla_con_mensaje_claro(notificacion, settings):
    settings.TELEGRAM_BOT_TOKEN = ""

    with pytest.raises(enviadores.ErrorEnvio, match="TELEGRAM_BOT_TOKEN"):
        enviadores.enviar_telegram(notificacion)


def test_telegram_sin_chat_id_falla(notificacion, token_falso, api_falsa):
    with pytest.raises(enviadores.ErrorEnvio, match="chat de Telegram"):
        enviadores.enviar_telegram(notificacion)
    assert api_falsa == []


def test_telegram_limite_de_velocidad_incluye_espera(
    notificacion, conductor, token_falso, monkeypatch
):
    notificacion.usuario = conductor.usuario
    def ocupado(token, metodo, datos=None, post=False):
        return {
            "ok": False,
            "error_code": 429,
            "description": "Too Many Requests",
            "parameters": {"retry_after": 12},
        }

    monkeypatch.setattr(enviadores, "telegram_api", ocupado)

    with pytest.raises(enviadores.ErrorEnvio, match="12 s"):
        enviadores.enviar_telegram(notificacion)


def test_correo_usa_la_bandeja_en_memoria(notificacion, conductor):
    notificacion.usuario = conductor.usuario

    enviadores.enviar_correo(notificacion)

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["carlos@ejemplo.com"]
    assert mail.outbox[0].subject == notificacion.titulo


def test_correo_sin_direccion_falla(notificacion, conductor):
    conductor.usuario.email = ""
    notificacion.usuario = conductor.usuario

    with pytest.raises(enviadores.ErrorEnvio, match="correo electrónico"):
        enviadores.enviar_correo(notificacion)


@pytest.fixture
def vapid_falso(settings):
    clave = ec.generate_private_key(ec.SECP256R1())
    pem = clave.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    settings.VAPID_PRIVATE_KEY_B64 = base64.b64encode(pem).decode("ascii")
    settings.VAPID_PUBLIC_KEY = "clave-publica-falsa"
    settings.VAPID_ADMIN_EMAIL = "avisos@ejemplo.com"
    settings.WEB_PUSH_TIMEOUT = 1


def test_web_push_envia_a_cada_suscripcion_activa(
    notificacion, conductor, vapid_falso, monkeypatch
):
    from apps.notificaciones.models import SuscripcionPush

    SuscripcionPush.objects.create(
        usuario=conductor.usuario,
        endpoint="https://push.example.com/uno",
        p256dh="abc",
        auth="def",
    )
    SuscripcionPush.objects.create(
        usuario=conductor.usuario,
        endpoint="https://push.example.com/dos",
        p256dh="ghi",
        auth="jkl",
        activa=False,
    )
    enviados = []

    def falso(subscription_info, **kwargs):
        enviados.append(subscription_info["endpoint"])

    monkeypatch.setattr(pywebpush, "webpush", falso)
    notificacion.usuario = conductor.usuario

    enviadores.enviar_web_push(notificacion)

    assert enviados == ["https://push.example.com/uno"]


def test_web_push_desactiva_suscripcion_caducada(
    notificacion, conductor, vapid_falso, monkeypatch
):
    from apps.notificaciones.models import SuscripcionPush

    suscripcion = SuscripcionPush.objects.create(
        usuario=conductor.usuario,
        endpoint="https://push.example.com/caducada",
        p256dh="abc",
        auth="def",
    )

    def caducada(subscription_info, **kwargs):
        raise pywebpush.WebPushException(
            "Gone", response=SimpleNamespace(status_code=410)
        )

    monkeypatch.setattr(pywebpush, "webpush", caducada)
    notificacion.usuario = conductor.usuario

    with pytest.raises(enviadores.ErrorEnvio, match="ninguna suscripción"):
        enviadores.enviar_web_push(notificacion)
    suscripcion.refresh_from_db()
    assert suscripcion.activa is False


def test_enviar_dispatch_por_canal(notificacion, monkeypatch):
    vistos = []
    monkeypatch.setattr(
        enviadores,
        "ENVIADORES",
        {Canal.CORREO: lambda notificacion: vistos.append("correo")},
    )

    enviadores.enviar(notificacion)

    assert vistos == ["correo"]
