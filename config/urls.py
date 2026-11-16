from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.maestros import views as maestros
from config.views import estado, inicio

urlpatterns = [
    path("admin/", admin.site.urls),
    # Rutas de acceso que trae Django: login, logout, cambio de contraseña.
    path("cuenta/", include("django.contrib.auth.urls")),
    # Capa web del contrato (§5.2 y §5.3).
    path("vehiculos/", include("apps.flota.urls")),
    path("documentos/", include("apps.flota.urls_documentos")),
    path("conductores/", maestros.ConductorListaView.as_view(), name="conductores"),
    path("maestros/", include("apps.maestros.urls")),
    path("estado/", estado, name="estado"),
    path("", inicio, name="inicio"),
]

# En desarrollo (DEBUG=True) Django sirve los archivos subidos desde MEDIA_ROOT.
# En producción eso lo hace el servidor web (nginx, IIS) y esta lista queda vacía.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
