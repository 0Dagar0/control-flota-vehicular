from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.flota.views import AlertasView, HojaVida360View, PanelView
from apps.flota.views_novedades import (
    AutorizarSalidaView,
    MisNovedadesView,
    NovedadGestionView,
    NovedadListaView,
    NovedadNuevaView,
)
from apps.maestros import views as maestros
from apps.servicio.views import InspeccionRapidaView, MiServicioView
from config.views import estado, inicio

urlpatterns = [
    path("admin/", admin.site.urls),
    # Rutas de acceso que trae Django: login, logout, cambio de contraseña.
    path("cuenta/", include("django.contrib.auth.urls")),
    # Capa web del contrato (§5.1 a §5.3).
    path("conductor/", MiServicioView.as_view(), name="mi_servicio"),
    path("servicio/", include("apps.servicio.urls")),
    path(
        "inspeccion/rapida/<str:placa>/",
        InspeccionRapidaView.as_view(),
        name="inspeccion_rapida",
    ),
    path("panel/", PanelView.as_view(), name="panel"),
    path("hoja-vida/<str:placa>/", HojaVida360View.as_view(), name="hoja_vida_360"),
    path("vehiculos/", include("apps.flota.urls")),
    path("documentos/", include("apps.flota.urls_documentos")),
    path("conductores/", maestros.ConductorListaView.as_view(), name="conductores"),
    path("alertas/", AlertasView.as_view(), name="alertas"),
    # v0.7: novedades del conductor y bandeja del administrador.
    path("novedades/nueva/", NovedadNuevaView.as_view(), name="novedad_nueva"),
    path("novedades/", NovedadListaView.as_view(), name="novedades"),
    path(
        "novedades/<int:pk>/gestion/",
        NovedadGestionView.as_view(),
        name="novedad_gestion",
    ),
    path(
        "novedades/<int:pk>/autorizar/",
        AutorizarSalidaView.as_view(),
        name="novedad_autorizar",
    ),
    path("mis-novedades/", MisNovedadesView.as_view(), name="mis_novedades"),
    path("maestros/", include("apps.maestros.urls")),
    path("estado/", estado, name="estado"),
    path("", inicio, name="inicio"),
]

# En desarrollo (DEBUG=True) Django sirve los archivos subidos desde MEDIA_ROOT.
# En producción eso lo hace el servidor web (nginx, IIS) y esta lista queda vacía.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
