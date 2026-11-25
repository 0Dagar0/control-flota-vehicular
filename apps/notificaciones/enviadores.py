"""Enviadores de los cuatro canales de la v1.0.

La intención de enviar y el resultado se guardan siempre en ``Notificacion``.
Los enviadores solo hacen la parte externa y lanzan ``ErrorEnvio`` con un
mensaje entendible; el comando ``enviar_notificaciones`` se encarga de reintentar.

No se usa ``requests`` para Telegram: con ``urllib`` basta y evita una
dependencia más para ese canal.
"""

from __future__ import annotations

import base64
import binascii
import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.mail import send_mail

from .models import Canal


class ErrorEnvio(Exception):
    """Fallo de un canal externo, con un mensaje listo para guardar y mostrar."""


def telegram_api(token: str, metodo: str, datos: dict | None = None, post: bool = False):
    """Llama a la API de Telegram y devuelve el JSON (incluso si hay error).

    Nunca incluye el token en el valor devuelto ni lo escribe en un registro.
    """

    url = f"{settings.TELEGRAM_API_URL}/bot{token}/{metodo}"
    try:
        if post:
            peticion = urllib.request.Request(
                url,
                data=json.dumps(datos or {}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
        else:
            if datos:
                url += "?" + urllib.parse.urlencode(datos)
            peticion = urllib.request.Request(url)
        with urllib.request.urlopen(peticion, timeout=settings.TELEGRAM_TIMEOUT) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            cuerpo = json.loads(error.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            cuerpo = {}
        cuerpo.setdefault("ok", False)
        cuerpo.setdefault("error_code", error.code)
        cuerpo.setdefault("description", "sin detalle")
        return cuerpo
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return {"ok": False, "description": f"No se pudo conectar: {error}"}


def enviar_app(notificacion) -> None:
    """El canal interno no envía nada: la fila en la bandeja ya es la entrega."""
    return None


def enviar_correo(notificacion) -> None:
    """Envía el aviso por SMTP usando la configuración ``MAILERS`` de Django."""
    destinatario = notificacion.usuario.email.strip()
    if not destinatario:
        raise ErrorEnvio("El usuario no tiene correo electrónico registrado.")
    try:
        enviados = send_mail(
            subject=notificacion.titulo,
            message=notificacion.mensaje,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[destinatario],
            fail_silently=False,
        )
    except Exception as error:  # noqa: BLE001 - se registra el tipo y el detalle
        raise ErrorEnvio(f"SMTP: {type(error).__name__}: {error}") from error
    if not enviados:
        raise ErrorEnvio("SMTP: el servidor no confirmó el envío.")


def enviar_telegram(notificacion) -> None:
    """Envía el aviso al chat privado guardado en ``Usuario.telegram_chat_id``."""

    token = settings.TELEGRAM_BOT_TOKEN.strip()
    chat_id = notificacion.usuario.telegram_chat_id.strip()
    if not token:
        raise ErrorEnvio("No hay TELEGRAM_BOT_TOKEN en el archivo .env.")
    if not chat_id:
        raise ErrorEnvio(
            "El usuario no tiene chat de Telegram: debe abrir el bot, pulsar Iniciar "
            "y guardar su chat_id."
        )

    texto = f"{notificacion.titulo}\n\n{notificacion.mensaje}"[:4096]
    respuesta = telegram_api(
        token,
        "sendMessage",
        {"chat_id": chat_id, "text": texto},
        post=True,
    )
    if not respuesta.get("ok"):
        espera = (respuesta.get("parameters") or {}).get("retry_after", "")
        detalle = f"Telegram {respuesta.get('error_code', '')}: {respuesta.get('description')}"
        if espera:
            detalle += f". Vuelve a intentarlo en {espera} s"
        raise ErrorEnvio(detalle)


def clave_privada_vapid() -> bytes:
    """Devuelve la clave privada VAPID en PEM, sin exponerla."""

    valor = settings.VAPID_PRIVATE_KEY_B64.strip()
    if not valor:
        raise ErrorEnvio("No hay VAPID_PRIVATE_KEY_B64 en el archivo .env.")
    try:
        return base64.b64decode(valor, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ErrorEnvio("La clave privada VAPID no es base64 válido.") from error


def enviar_web_push(notificacion) -> None:
    """Envía el aviso a todos los navegadores suscritos de ese usuario."""

    from pywebpush import WebPushException, webpush

    suscripciones = list(notificacion.usuario.suscripciones_push.filter(activa=True))
    if not suscripciones:
        raise ErrorEnvio("El usuario no tiene suscripciones Web Push activas.")
    if not settings.VAPID_PUBLIC_KEY or not settings.VAPID_ADMIN_EMAIL:
        raise ErrorEnvio("Faltan VAPID_PUBLIC_KEY o VAPID_ADMIN_EMAIL en el .env.")

    datos = json.dumps(
        {
            "titulo": notificacion.titulo,
            "mensaje": notificacion.mensaje,
            "url": notificacion.url,
            "evento": notificacion.evento,
        },
        ensure_ascii=False,
    )
    privada = clave_privada_vapid()
    entregas = 0
    for suscripcion in suscripciones:
        try:
            webpush(
                subscription_info={
                    "endpoint": suscripcion.endpoint,
                    "keys": {
                        "p256dh": suscripcion.p256dh,
                        "auth": suscripcion.auth,
                    },
                },
                data=datos,
                vapid_private_key=privada,
                vapid_claims={"sub": f"mailto:{settings.VAPID_ADMIN_EMAIL}"},
                timeout=settings.WEB_PUSH_TIMEOUT,
            )
            entregas += 1
        except WebPushException as error:
            codigo = getattr(getattr(error, "response", None), "status_code", None)
            # 404/410: el navegador ya no existe; se desactiva y no se reintenta.
            if codigo in (404, 410):
                suscripcion.activa = False
                suscripcion.save(update_fields=["activa"])
                continue
            raise ErrorEnvio(f"Web Push {codigo or ''}: {error}") from error
        except Exception as error:  # noqa: BLE001 - error de red o de firma
            raise ErrorEnvio(f"Web Push: {type(error).__name__}: {error}") from error
    if not entregas:
        raise ErrorEnvio("Web Push: ninguna suscripción sigue activa (404/410).")


ENVIADORES = {
    Canal.APP: enviar_app,
    Canal.CORREO: enviar_correo,
    Canal.TELEGRAM: enviar_telegram,
    Canal.WEB_PUSH: enviar_web_push,
}


def enviar(notificacion) -> None:
    """Busca el enviador del canal y lanza ``ErrorEnvio`` si no existe."""
    funcion = ENVIADORES.get(notificacion.canal)
    if funcion is None:
        raise ErrorEnvio(f"Canal desconocido: {notificacion.canal}")
    funcion(notificacion)
