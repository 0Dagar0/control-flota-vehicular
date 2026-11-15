"""Vistas de la flota: lista de vehículos, hoja de vida y documentos.

Permisos (v0.3): solo administradores y superadministradores ven la flota. Un
conductor no puede entrar todavía porque su pantalla llega en v0.5.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.views.generic import DetailView, ListView

from .models import Documento, FotoVehiculo, Vehiculo


class AccesoFlotaMixin(LoginRequiredMixin):
    """Exige sesión iniciada y un rol con acceso a la flota."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.es_admin:
            raise PermissionDenied("Tu rol no tiene acceso a esta sección.")
        return super().dispatch(request, *args, **kwargs)


class VehiculoListaView(AccesoFlotaMixin, ListView):
    """Tabla de vehículos con documentos y fotos pendientes."""

    model = Vehiculo
    template_name = "flota/vehiculo_lista.html"
    context_object_name = "vehiculos"

    def get_queryset(self):
        return Vehiculo.objects.annotate(
            total_documentos=Count("documentos", distinct=True),
            documentos_sin_soporte=Count(
                "documentos", filter=Q(documentos__soporte=""), distinct=True
            ),
            total_fotos=Count("fotos", distinct=True),
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["seccion"] = "vehiculos"
        return contexto


class VehiculoDetalleView(AccesoFlotaMixin, DetailView):
    """Hoja de vida: datos, documentos con semáforo y fotos."""

    model = Vehiculo
    template_name = "flota/vehiculo_detalle.html"
    context_object_name = "vehiculo"
    # La URL usa la placa en lugar del id numérico.
    slug_field = "placa"
    slug_url_kwarg = "placa"

    def get_queryset(self):
        return Vehiculo.objects.prefetch_related("documentos", "fotos")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["seccion"] = "vehiculos"
        contexto["documentos"] = self.object.documentos.all()
        contexto["fotos"] = self.object.fotos.all()
        # Un espacio por cada tipo de foto, con su imagen más reciente (o vacío).
        ultimas = {}
        for foto in self.object.fotos.all():
            ultimas.setdefault(foto.tipo, foto)
        contexto["espacios_foto"] = [
            {"clave": clave, "etiqueta": etiqueta, "foto": ultimas.get(clave)}
            for clave, etiqueta in FotoVehiculo.Tipo.choices
        ]
        return contexto


class DocumentoListaView(AccesoFlotaMixin, ListView):
    """Todos los documentos, con filtro por soporte pendiente."""

    model = Documento
    template_name = "flota/documento_lista.html"
    context_object_name = "documentos"

    def get_queryset(self):
        consulta = Documento.objects.select_related("vehiculo", "conductor")
        if self.request.GET.get("soporte") == "pendiente":
            consulta = consulta.filter(soporte="")
        return consulta.order_by("vencimiento")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["seccion"] = "documentos"
        contexto["solo_pendientes"] = self.request.GET.get("soporte") == "pendiente"
        contexto["total_pendientes"] = Documento.objects.filter(soporte="").count()
        return contexto
