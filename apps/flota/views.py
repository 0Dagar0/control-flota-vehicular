"""Vistas de la flota: lista de vehículos, hoja de vida y documentos.

Permisos (v0.3): solo administradores y superadministradores ven la flota. Un
conductor no puede entrar todavía porque su pantalla llega en v0.5.
"""

from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Exists, OuterRef, Q
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView

from .models import Asignacion, Conductor, Documento, FotoVehiculo, Servicio, Vehiculo


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


class AlertasView(AccesoFlotaMixin, TemplateView):
    """Centro de alertas con datos reales de los modelos disponibles en v0.5.

    Solo se calculan los hechos que existen hoy: documentos, licencias, servicios
    abiertos, conductores sin vehículo y vehículos sin fotos. Los mantenimientos
    y las novedades críticas se añadirán con sus modelos (v0.6 y v0.7); mientras
    tanto no se inventan alertas.
    """

    template_name = "flota/alertas.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        hoy = timezone.localdate()
        ahora = timezone.now()
        criticas, proximas, informativas = [], [], []

        def agregar(destino, icono, titulo, meta, descripcion, url, boton):
            destino.append(
                {
                    "icono": icono,
                    "titulo": titulo,
                    "meta": meta,
                    "descripcion": descripcion,
                    "url": url,
                    "boton": boton,
                }
            )

        # R11: documento vencido del vehículo. La licencia se contabiliza aparte
        # desde el conductor, para que un mismo hecho no aparezca dos veces.
        vencidos = (
            Documento.objects.filter(vencimiento__lt=hoy)
            .exclude(tipo=Documento.Tipo.LICENCIA)
            .select_related("vehiculo")
        )
        for documento in vencidos:
            placa = documento.vehiculo.placa
            agregar(
                criticas,
                "📄",
                f"{documento.get_tipo_display()} vencido",
                f"{placa} · venció el {documento.vencimiento:%d/%m/%Y}",
                "El vehículo no puede salir a reparto hasta renovar el documento "
                "y cargar el soporte.",
                reverse("flota:detalle", args=[placa]),
                "Ver vehículo",
            )

        # R21: licencia vencida de un conductor que sigue activo.
        for conductor in Conductor.objects.filter(
            activo=True, licencia_vencimiento__lt=hoy
        ).select_related("usuario"):
            agregar(
                criticas,
                "🪪",
                "Licencia vencida",
                f"{conductor} · categoría {conductor.get_licencia_categoria_display()} · "
                f"venció el {conductor.licencia_vencimiento:%d/%m/%Y}",
                "Figura como «No habilitado (licencia)»: no puede iniciar servicio, "
                "pero el vehículo no se bloquea por esto.",
                reverse("conductores"),
                "Ver conductores",
            )

        # Umbrales del contrato §9: 7 y 3 días antes del vencimiento.
        por_vencer = (
            Documento.objects.filter(
                vencimiento__gte=hoy, vencimiento__lte=hoy + timedelta(days=7)
            )
            .exclude(tipo=Documento.Tipo.LICENCIA)
            .select_related("vehiculo")
        )
        for documento in por_vencer:
            placa = documento.vehiculo.placa
            dias = (documento.vencimiento - hoy).days
            agregar(
                proximas,
                "🗓️",
                f"{documento.get_tipo_display()} por vencer en {dias} días",
                f"{placa} · vence el {documento.vencimiento:%d/%m/%Y}",
                "Cargar el soporte antes del vencimiento evita que el vehículo quede bloqueado.",
                reverse("flota:detalle", args=[placa]),
                "Abrir hoja de vida",
            )

        # Servicios abiertos durante más de 12 horas.
        abiertos = Servicio.objects.filter(
            cerrado_en__isnull=True, iniciado_en__lte=ahora - timedelta(hours=12)
        ).select_related("vehiculo", "conductor")
        for servicio in abiertos:
            agregar(
                proximas,
                "⏱️",
                "Servicio abierto hace más de 12 horas",
                f"{servicio.vehiculo.placa} · {servicio.conductor} · "
                f"iniciado el {servicio.iniciado_en:%d/%m/%Y a las %H:%M}",
                "Falta cerrar el servicio con el kilometraje final.",
                reverse("conductores"),
                "Ver conductores",
            )

        # Conductores activos a los que nadie les ha asignado vehículo.
        sin_asignacion = Conductor.objects.filter(activo=True).filter(
            ~Exists(
                Asignacion.objects.filter(
                    conductor=OuterRef("pk"), fecha_fin__isnull=True
                )
            )
        )
        for conductor in sin_asignacion:
            agregar(
                informativas,
                "👤",
                "Conductor activo sin vehículo asignado",
                str(conductor),
                "Al entrar verá la pantalla «Todavía no tienes vehículo asignado».",
                reverse("conductores"),
                "Ver conductores",
            )

        # Vehículos activos sin ninguna de las seis fotos de referencia.
        sin_fotos = Vehiculo.objects.filter(activo=True).annotate(
            total_fotos=Count("fotos")
        ).filter(total_fotos=0)
        for vehiculo in sin_fotos:
            agregar(
                informativas,
                "📷",
                "Vehículo sin fotos registradas",
                f"{vehiculo.placa} · 0 de 6 fotos",
                "Faltan las fotos de referencia: frontal, trasera, laterales, cabina y tablero.",
                reverse("flota:detalle", args=[vehiculo.placa]),
                "Ver fotos",
            )

        # Cierres recientes con novedad, para seguimiento del administrador.
        con_novedad = Servicio.objects.filter(
            cerrado_en__gte=ahora - timedelta(days=7), sin_novedad=False
        ).select_related("vehiculo")[:5]
        for servicio in con_novedad:
            agregar(
                informativas,
                "✅",
                "Servicio cerrado con novedad",
                f"{servicio.vehiculo.placa} · {servicio.cerrado_en:%d/%m/%Y}",
                servicio.observacion_cierre or "El cierre quedó marcado con novedad.",
                reverse("flota:detalle", args=[servicio.vehiculo.placa]),
                "Ver vehículo",
            )

        contexto["seccion"] = "alertas"
        contexto["grupos"] = [
            {
                "clave": "critico",
                "titulo": "Crítico",
                "descripcion": "Requiere acción hoy: el vehículo o el conductor no pueden operar.",
                "alertas": criticas,
            },
            {
                "clave": "proximo",
                "titulo": "Próximo",
                "descripcion": "Se resuelve en los próximos días; si se deja pasar, "
                "se vuelve crítico.",
                "alertas": proximas,
            },
            {
                "clave": "info",
                "titulo": "Informativo",
                "descripcion": "No exige acción inmediata, pero conviene revisarlo.",
                "alertas": informativas,
            },
        ]
        contexto["total_alertas"] = len(criticas) + len(proximas) + len(informativas)
        return contexto
