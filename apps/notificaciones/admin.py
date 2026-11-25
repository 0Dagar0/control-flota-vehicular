"""Administración de notificaciones (solo lectura del historial)."""

from django.contrib import admin

from .models import Notificacion, PreferenciaNotificacion, SuscripcionPush


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = (
        "creado_en",
        "usuario",
        "evento",
        "canal",
        "estado",
        "intentos",
        "enviado_en",
        "leida_en",
    )
    list_filter = ("evento", "canal", "estado")
    search_fields = ("titulo", "mensaje", "usuario__documento", "referencia")
    readonly_fields = ("creado_en", "enviado_en", "leida_en", "intentos", "error")
    date_hierarchy = "creado_en"


@admin.register(PreferenciaNotificacion)
class PreferenciaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "correo", "telegram", "web_push", "resumen_diario")


@admin.register(SuscripcionPush)
class SuscripcionPushAdmin(admin.ModelAdmin):
    list_display = ("usuario", "activa", "creado_en")
    list_filter = ("activa",)
    search_fields = ("usuario__documento", "endpoint")
