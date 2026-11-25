"""Pruebas de las pantallas de notificaciones y del alta Web Push."""

import json

import pytest
from django.urls import reverse

from ..models import Estado, PreferenciaNotificacion, SuscripcionPush


@pytest.fixture
def en_sesion(client, admin):
    client.force_login(admin)
    return admin


def test_bandeja_muestra_la_notificacion(client, en_sesion, notificacion):
    respuesta = client.get(reverse("notificaciones:lista"))

    assert respuesta.status_code == 200
    assert "Novedad crítica" in respuesta.content.decode("utf-8")


def test_filtro_por_canal_deja_estado_vacio(client, en_sesion, notificacion):
    respuesta = client.get(reverse("notificaciones:lista"), {"canal": "telegram"})

    assert respuesta.status_code == 200
    assert "No tienes notificaciones con estos filtros" in respuesta.content.decode("utf-8")


def test_marcar_todas_como_leidas(client, en_sesion, notificacion):
    respuesta = client.post(reverse("notificaciones:marcar_todas"))

    assert respuesta.status_code == 204
    notificacion.refresh_from_db()
    assert notificacion.estado == Estado.LEIDA
    assert notificacion.leida_en is not None


def test_detalle_y_marcar_leida(client, en_sesion, notificacion):
    detalle = client.get(reverse("notificaciones:detalle", args=[notificacion.pk]))
    assert detalle.status_code == 200
    assert "Estado de los canales" in detalle.content.decode("utf-8")

    respuesta = client.post(
        reverse("notificaciones:marcar_leida", args=[notificacion.pk])
    )
    assert respuesta.status_code == 204
    notificacion.refresh_from_db()
    assert notificacion.leida_en is not None


def test_no_se_puede_leer_notificacion_de_otro_usuario(
    client, en_sesion, superadmin, notificacion
):
    client.force_login(superadmin)

    assert client.get(reverse("notificaciones:detalle", args=[notificacion.pk])).status_code == 404


def test_preferencias_se_guardan(client, en_sesion):
    url = reverse("notificaciones:preferencias")
    assert client.get(url).status_code == 200

    respuesta = client.post(
        url,
        {
            "telegram": "on",
            "web_push": "on",
            "resumen_diario": "on",
            "hora_resumen": "08:30",
        },
    )

    assert respuesta.status_code == 302
    preferencia = PreferenciaNotificacion.objects.get(usuario=en_sesion)
    assert preferencia.correo is False
    assert preferencia.hora_resumen.strftime("%H:%M") == "08:30"


def test_canales_solo_superadmin_y_sin_secretos(client, en_sesion, settings, superadmin):
    settings.TELEGRAM_BOT_TOKEN = "123456789:AAtokenSecretoNoMostrar123456789"
    url = reverse("notificaciones:canales")

    assert client.get(url).status_code == 403
    client.force_login(superadmin)
    respuesta = client.get(url)
    contenido = respuesta.content.decode("utf-8")

    assert respuesta.status_code == 200
    assert "Web Push (VAPID)" in contenido
    assert settings.TELEGRAM_BOT_TOKEN not in contenido
    assert "••••••••" in contenido


def test_resumen_diario_se_puede_previsualizar(client, en_sesion):
    respuesta = client.get(reverse("notificaciones:resumen_diario"))

    assert respuesta.status_code == 200
    assert "Resumen diario" in respuesta.content.decode("utf-8")


def test_suscribir_push_valido(client, en_sesion):
    cuerpo = {
        "endpoint": "https://push.example.com/navegador",
        "keys": {"p256dh": "clave-publica", "auth": "clave-auth"},
    }

    respuesta = client.post(
        reverse("notificaciones:suscribir"),
        data=json.dumps(cuerpo),
        content_type="application/json",
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["ok"] is True
    assert SuscripcionPush.objects.filter(usuario=en_sesion).count() == 1


def test_suscribir_push_rechaza_endpoint_inseguro(client, en_sesion):
    cuerpo = {
        "endpoint": "http://push.example.com/navegador",
        "keys": {"p256dh": "abc", "auth": "def"},
    }

    respuesta = client.post(
        reverse("notificaciones:suscribir"),
        data=json.dumps(cuerpo),
        content_type="application/json",
    )

    assert respuesta.status_code == 400
    assert SuscripcionPush.objects.count() == 0


def test_service_worker_se_sirve_desde_la_raiz(client):
    respuesta = client.get("/sw.js")

    assert respuesta.status_code == 200
    assert respuesta.headers["Content-Type"] == "application/javascript"
    assert respuesta.headers["Service-Worker-Allowed"] == "/"
