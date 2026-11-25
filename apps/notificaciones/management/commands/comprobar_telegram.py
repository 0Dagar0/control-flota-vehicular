"""Comprueba el bot de Telegram sin mostrar el token.

Uso (desde la carpeta ``App``)::

    .venv\\Scripts\\python.exe manage.py comprobar_telegram
    .venv\\Scripts\\python.exe manage.py comprobar_telegram --sin-envio
    .venv\\Scripts\\python.exe manage.py comprobar_telegram --chat-id 123456789

Sin ``--chat-id`` busca el último chat privado que haya escrito al bot. El token
se lee del ``.env`` y nunca se imprime.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.notificaciones.enviadores import telegram_api

MENSAJE = (
    "Mi Flota - comprobación de Telegram.\n\n"
    "Si lees esto, el bot puede enviar avisos. No respondas a este mensaje."
)


class Command(BaseCommand):
    help = "Verifica el token del bot y envía un mensaje de prueba a un chat."

    def add_arguments(self, parser):
        parser.add_argument(
            "--chat-id",
            default="",
            help="Chat privado de destino. Si se omite, se toma el último mensaje recibido.",
        )
        parser.add_argument(
            "--sin-envio",
            action="store_true",
            help="Solo comprueba el token; no envía ningún mensaje.",
        )

    def ultimo_chat_privado(self, token: str):
        respuesta = telegram_api(token, "getUpdates", {"timeout": 0})
        if not respuesta.get("ok"):
            raise CommandError(
                "Telegram rechazó getUpdates: "
                f"{respuesta.get('error_code', '')} {respuesta.get('description', '')}"
            )
        for actualizacion in reversed(respuesta.get("result", [])):
            mensaje = actualizacion.get("message") or actualizacion.get("edited_message")
            chat = (mensaje or {}).get("chat") or {}
            if chat.get("type") == "private":
                return chat
        return None

    def handle(self, *args, **opciones):
        token = settings.TELEGRAM_BOT_TOKEN.strip()
        if not token or token.startswith("<"):
            raise CommandError(
                "Falta TELEGRAM_BOT_TOKEN en App\\.env. Pega allí el token de @BotFather."
            )
        if ":" not in token or not token.split(":", 1)[0].isdigit():
            raise CommandError(
                "El token no tiene el formato esperado (números, dos puntos y letras). "
                "Revisa que no tenga espacios ni comillas."
            )

        yo = telegram_api(token, "getMe")
        if not yo.get("ok"):
            raise CommandError(
                f"Telegram rechazó el token: {yo.get('error_code', '')} "
                f"{yo.get('description', 'sin detalle')}. Si se filtró, usa /revoke en BotFather."
            )
        bot = yo["result"]
        self.stdout.write(
            self.style.SUCCESS(
                f"Bot OK: @{bot.get('username')} (id={bot.get('id')}, "
                f"nombre={bot.get('first_name')})."
            )
        )
        if opciones["sin_envio"]:
            return

        chat_id = str(opciones["chat_id"] or "").strip()
        chat = None
        if not chat_id:
            chat = self.ultimo_chat_privado(token)
            if chat:
                chat_id = str(chat["id"])
        if not chat_id:
            self.stdout.write(
                self.style.WARNING(
                    "No hay ningún chat iniciado. Abre https://t.me/"
                    f"{bot.get('username')}, pulsa Iniciar, envía hola y repite."
                )
            )
            return

        respuesta = telegram_api(
            token,
            "sendMessage",
            {"chat_id": chat_id, "text": MENSAJE},
            post=True,
        )
        if not respuesta.get("ok"):
            raise CommandError(
                f"No se pudo enviar: {respuesta.get('error_code', '')} "
                f"{respuesta.get('description', 'sin detalle')}"
            )
        nombre = (chat or {}).get("first_name", "chat indicado")
        self.stdout.write(
            self.style.SUCCESS(
                f"Mensaje de prueba enviado a {nombre} (chat_id={chat_id})."
            )
        )
