"""Configuración común de las pruebas.

Los correos de las pruebas nunca salen a Internet: se guardan en la bandeja en
memoria de Django, aunque el `.env` tenga credenciales SMTP reales.
"""

import pytest


@pytest.fixture(autouse=True)
def correo_en_memoria(settings):
    settings.MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.locmem.EmailBackend",
        },
    }
    settings.DEFAULT_FROM_EMAIL = "Mi Flota <pruebas@ejemplo.com>"
