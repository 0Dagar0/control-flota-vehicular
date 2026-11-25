"""Rutas de notificaciones (v1.0)."""

from django.urls import path

from . import views

app_name = "notificaciones"

urlpatterns = [
    path("", views.BandejaView.as_view(), name="lista"),
    path("<int:pk>/", views.NotificacionDetalleView.as_view(), name="detalle"),
    path("<int:pk>/leer/", views.MarcarLeidaView.as_view(), name="marcar_leida"),
    path("marcar-todas/", views.MarcarTodasLeidasView.as_view(), name="marcar_todas"),
    path("preferencias/", views.PreferenciasView.as_view(), name="preferencias"),
    path("canales/", views.CanalesView.as_view(), name="canales"),
    path("resumen-diario/", views.ResumenDiarioView.as_view(), name="resumen_diario"),
    path("suscribir/", views.SuscribirPushView.as_view(), name="suscribir"),
]
