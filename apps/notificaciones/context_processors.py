"""Contador de notificaciones sin leer para el menú lateral."""


def badge(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"notificaciones_sin_leer": 0}
    return {
        "notificaciones_sin_leer": request.user.notificaciones.filter(
            leida_en__isnull=True
        ).count()
    }
