"""Vistas del proyecto (no pertenecen a una app concreta)."""

import django
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.shortcuts import redirect, render


def inicio(request):
    """Portada: manda a cada rol a la pantalla que le corresponde."""
    if not request.user.is_authenticated:
        return redirect("login")
    if request.user.es_admin:
        return redirect("flota:lista")
    # El conductor todavía no tiene pantallas propias (llegan en v0.5).
    return render(request, "pendiente.html", {"seccion": "panel"})


def estado(request):
    """Página de verificación del entorno (solo para desarrollo)."""
    Usuario = get_user_model()
    contexto = {
        "django_version": django.get_version(),
        "motor_bd": connection.vendor,
        "debug": settings.DEBUG,
        "total_usuarios": Usuario.objects.count(),
    }
    return render(request, "inicio.html", contexto)
