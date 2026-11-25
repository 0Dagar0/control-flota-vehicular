"""Pruebas del comando `comprobar_correo` (verificación del envío SMTP)."""

from io import StringIO

import pytest
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError

CONSOLA = {
    "default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"},
}


@pytest.fixture
def consola(settings):
    """Deja el mailer como consola, como en un equipo sin credenciales."""
    settings.MAILERS = CONSOLA


def test_envia_la_prueba_al_destinatario_indicado():
    call_command("comprobar_correo", "--para", "dueno@ejemplo.com")

    assert len(mail.outbox) == 1
    correo = mail.outbox[0]
    assert correo.to == ["dueno@ejemplo.com"]
    assert "prueba" in correo.subject.lower()
    assert "SMTP funciona" in correo.body


def test_sin_para_usa_el_remitente_configurado(settings):
    settings.CORREO_REMITENTE = "miflota.granjero@gmail.com"

    call_command("comprobar_correo")

    assert mail.outbox[0].to == ["miflota.granjero@gmail.com"]


def test_sin_destinatario_ni_remitente_falla(settings):
    settings.CORREO_REMITENTE = ""

    with pytest.raises(CommandError):
        call_command("comprobar_correo")


def test_avisa_si_no_hay_smtp_configurado(consola):
    salida = StringIO()

    call_command("comprobar_correo", "--para", "dueno@ejemplo.com", stdout=salida)

    assert "consola" in salida.getvalue()
