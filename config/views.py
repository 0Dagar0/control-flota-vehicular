"""Vistas del proyecto (no pertenecen a una app concreta)."""

import django
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.shortcuts import render


def inicio(request):
    """Página de bienvenida y verificación del entorno."""
    Usuario = get_user_model()
    contexto = {
        "django_version": django.get_version(),
        "motor_bd": connection.vendor,
        "debug": settings.DEBUG,
        "total_usuarios": Usuario.objects.count(),
    }
    return render(request, "inicio.html", contexto)
