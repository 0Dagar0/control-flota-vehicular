"""Configuración de la app de notificaciones (v1.0)."""

from django.apps import AppConfig


class NotificacionesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notificaciones"
    verbose_name = "Notificaciones"
