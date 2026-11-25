"""Envía un correo de prueba para comprobar la configuración SMTP.

Sirve para verificar la contraseña de aplicación de Gmail antes de construir la
v1.0. Si falla, traduce el error técnico a una causa probable.

En Django 6 la configuración vive en ``settings.MAILERS``; las variables del
``.env`` se siguen llamando ``EMAIL_*`` para que coincidan con la documentación
de Gmail y de otros proveedores.

Uso (desde la carpeta ``App``)::

    .venv\\Scripts\\python.exe manage.py comprobar_correo
    .venv\\Scripts\\python.exe manage.py comprobar_correo --para otro@correo.com
"""

import smtplib

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError

ASUNTO = "Mi Flota - prueba de correo"
CUERPO = (
    "Este es un correo de prueba de Mi Flota.\n\n"
    "Si lo estás leyendo, el envío por SMTP funciona y los avisos de documentos, "
    "inspecciones y novedades podrán salir por este canal.\n\n"
    "No respondas a este mensaje: la cuenta solo se usa para enviar avisos."
)


def opciones_smtp():
    """Devuelve las opciones del mailer «default» (vacías si es consola)."""
    return settings.MAILERS.get("default", {}).get("OPTIONS", {})


class Command(BaseCommand):
    help = "Envía un correo de prueba y explica el error si el envío falla."

    def add_arguments(self, parser):
        parser.add_argument(
            "--para",
            default="",
            help="Destinatario de la prueba (por defecto, el remitente configurado).",
        )

    def handle(self, *args, **opciones):
        smtp = opciones_smtp()
        destinatario = opciones["para"] or settings.CORREO_REMITENTE
        if not destinatario:
            raise CommandError(
                "No hay destinatario: pasa --para correo@dominio.com o configura "
                "EMAIL_HOST_USER en el archivo .env."
            )
        if not smtp.get("host"):
            self.stdout.write(
                self.style.WARNING(
                    "No hay EMAIL_HOST en el .env: el correo se imprime en esta consola "
                    "y no se envía de verdad."
                )
            )

        try:
            enviados = send_mail(
                subject=ASUNTO,
                message=CUERPO,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[destinatario],
            )
        except smtplib.SMTPAuthenticationError as error:
            raise CommandError(
                "Gmail rechazó el usuario o la contraseña. Revisa que EMAIL_HOST_USER sea "
                "la cuenta completa y que EMAIL_HOST_PASSWORD sea la contraseña de "
                "aplicación de 16 caracteres (no la de la cuenta)."
            ) from error
        except smtplib.SMTPException as error:
            raise CommandError(f"El servidor SMTP devolvió un error: {error}") from error
        except OSError as error:
            raise CommandError(
                f"No se pudo conectar con {smtp.get('host')}:{smtp.get('port', 25)}. "
                f"Revisa la conexión, el puerto y el firewall. Detalle: {error}"
            ) from error

        if enviados:
            self.stdout.write(
                self.style.SUCCESS(f"Correo de prueba enviado a {destinatario}.")
            )
        else:
            self.stdout.write(
                self.style.WARNING("El backend no envió ningún correo (revisa MAILERS).")
            )
