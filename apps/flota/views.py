"""Vistas de la flota: lista de vehículos, hoja de vida y documentos.

Permisos (v0.3): solo administradores y superadministradores ven la flota. Un
conductor no puede entrar todavía porque su pantalla llega en v0.5.
"""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Exists, OuterRef, Q
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView

from .forms_documentos import DocumentoRenovarForm
from .forms_fotos import FotoVehiculoForm
from .forms_mantenimiento import IncidenteForm, MantenimientoForm
from .models import (
    Asignacion,
    Conductor,
    Documento,
    FotoVehiculo,
    Incidente,
    Inspeccion,
    Mantenimiento,
    Novedad,
    Servicio,
    Vehiculo,
)


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


class VehiculoFotosView(AccesoFlotaMixin, TemplateView):
    """Galería de las 6 fotos del vehículo, con carga y historial."""

    template_name = "flota/vehiculo_fotos.html"

    def get_vehiculo(self):
        return get_object_or_404(Vehiculo, placa=self.kwargs["placa"])

    def contexto(self, vehiculo, form=None, tipo_con_error=""):
        fotos = list(vehiculo.fotos.select_related("subido_por"))
        ultimas = {}
        versiones = {}
        for foto in fotos:
            ultimas.setdefault(foto.tipo, foto)
            versiones[foto.tipo] = versiones.get(foto.tipo, 0) + 1
        espacios = [
            {
                "clave": clave,
                "etiqueta": etiqueta,
                "foto": ultimas.get(clave),
                "versiones": versiones.get(clave, 0),
            }
            for clave, etiqueta in FotoVehiculo.Tipo.choices
        ]
        return {
            "seccion": "vehiculos",
            "vehiculo": vehiculo,
            "espacios": espacios,
            "form": form,
            "tipo_con_error": tipo_con_error,
        }

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.contexto(self.get_vehiculo()))

    def post(self, request, *args, **kwargs):
        vehiculo = self.get_vehiculo()
        tipo = request.POST.get("tipo", "")
        if tipo not in dict(FotoVehiculo.Tipo.choices):
            messages.error(request, "El tipo de foto no es válido.")
            return redirect("flota:fotos", placa=vehiculo.placa)
        foto = FotoVehiculo(vehiculo=vehiculo, tipo=tipo, subido_por=request.user)
        form = FotoVehiculoForm(request.POST, request.FILES, instance=foto)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"Foto «{foto.get_tipo_display()}» guardada para {vehiculo.placa}.",
            )
            return redirect("flota:fotos", placa=vehiculo.placa)
        return render(request, self.template_name, self.contexto(vehiculo, form, tipo))


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


class DocumentoRenovarView(AccesoFlotaMixin, TemplateView):
    """Renueva el vencimiento de un documento (v0.9)."""

    template_name = "flota/documento_renovar.html"

    def get_documento(self):
        return get_object_or_404(
            Documento.objects.select_related("vehiculo", "conductor"),
            pk=self.kwargs["pk"],
        )

    def contexto(self, documento, form=None):
        return {
            "seccion": "documentos",
            "documento": documento,
            "form": form or DocumentoRenovarForm(instance=documento),
        }

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.contexto(self.get_documento()))

    def post(self, request, *args, **kwargs):
        documento = self.get_documento()
        form = DocumentoRenovarForm(request.POST, request.FILES, instance=documento)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"Documento renovado: nuevo vencimiento {documento.vencimiento:%d/%m/%Y}.",
            )
            return redirect("documentos:lista")
        return render(request, self.template_name, self.contexto(documento, form))


class PanelView(AccesoFlotaMixin, TemplateView):
    """Panel de indicadores: cumplimiento, bloqueos y fallas repetidas (v0.10)."""

    template_name = "flota/panel.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        vehiculos = list(Vehiculo.objects.all())
        bloqueados = [
            vehiculo
            for vehiculo in vehiculos
            if vehiculo.estado
            in (Vehiculo.Estado.BLOQUEADO_DOCUMENTO, Vehiculo.Estado.BLOQUEADO_NOVEDAD)
        ]
        fallas = (
            Novedad.objects.annotate(descripcion_normal=Lower("descripcion"))
            .values("vehiculo__placa", "descripcion_normal")
            .annotate(total=Count("pk"))
            .filter(total__gt=1)
            .order_by("-total")[:8]
        )
        contexto.update(
            {
                "seccion": "panel",
                "vehiculos": vehiculos,
                "total_vehiculos": len(vehiculos),
                "bloqueados": bloqueados,
                "total_bloqueados": len(bloqueados),
                "novedades_abiertas": Novedad.objects.filter(
                    estado=Novedad.Estado.ABIERTA
                ).count(),
                "cumplimiento_promedio": (
                    round(
                        sum(v.cumplimiento_documental for v in vehiculos) / len(vehiculos)
                    )
                    if vehiculos
                    else 0
                ),
                "fallas_repetidas": fallas,
                "inspecciones_hoy": Inspeccion.objects.filter(
                    iniciado_en__date=timezone.localdate()
                ).count(),
            }
        )
        return contexto


class HojaVida360View(AccesoFlotaMixin, DetailView):
    """Vista 360° de un vehículo: documentos, inspecciones, novedades y más (v0.10)."""

    model = Vehiculo
    template_name = "flota/hoja_vida_360.html"
    context_object_name = "vehiculo"
    slug_field = "placa"
    slug_url_kwarg = "placa"

    def get_queryset(self):
        return Vehiculo.objects.prefetch_related("documentos", "fotos")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        vehiculo = self.object
        # Una foto por ángulo: la más reciente de cada tipo (el resto es historial).
        ultimas_fotos = {}
        for foto in vehiculo.fotos.all():
            ultimas_fotos.setdefault(foto.tipo, foto)
        contexto.update(
            {
                "seccion": "vehiculos",
                "documentos": vehiculo.documentos.all(),
                "inspecciones": vehiculo.inspecciones.select_related("conductor")[:5],
                "novedades": vehiculo.novedades.select_related("conductor")[:5],
                "fotos": list(ultimas_fotos.values()),
                "servicios": vehiculo.servicios.select_related("conductor")[:5],
                "asignaciones": vehiculo.asignaciones.select_related("conductor")[:5],
                "mantenimientos": vehiculo.mantenimientos.all()[:5],
                "incidentes": vehiculo.incidentes.all()[:5],
                "cumplimiento_documental": vehiculo.cumplimiento_documental,
                "ultima_inspeccion": vehiculo.inspecciones.first(),
            }
        )
        return contexto


class MantenimientoListaView(AccesoFlotaMixin, ListView):
    """Histórico de mantenimientos con el aviso de próximo km (R16/R17)."""

    model = Mantenimiento
    template_name = "flota/mantenimiento_lista.html"
    context_object_name = "mantenimientos"

    def get_queryset(self):
        consulta = Mantenimiento.objects.select_related("vehiculo")
        placa = self.request.GET.get("vehiculo", "").strip()
        if placa:
            consulta = consulta.filter(vehiculo__placa__icontains=placa)
        listado = list(consulta.order_by("proximo_km", "-fecha"))
        estado = self.request.GET.get("estado")
        if estado:
            listado = [item for item in listado if item.estado_semforo == estado]
        return listado

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["seccion"] = "mantenimientos"
        return contexto


class MantenimientoNuevoView(AccesoFlotaMixin, TemplateView):
    template_name = "flota/mantenimiento_nuevo.html"

    def get(self, request, *args, **kwargs):
        return render(
            request,
            self.template_name,
            {"seccion": "mantenimientos", "form": MantenimientoForm()},
        )

    def post(self, request, *args, **kwargs):
        form = MantenimientoForm(request.POST, request.FILES)
        if form.is_valid():
            mantenimiento = form.save(commit=False)
            mantenimiento.creado_por = request.user
            mantenimiento.save()
            messages.success(
                request,
                f"Mantenimiento registrado para {mantenimiento.vehiculo.placa}. "
                f"{mantenimiento.mensaje_km}.",
            )
            return redirect("mantenimientos")
        return render(
            request, self.template_name, {"seccion": "mantenimientos", "form": form}
        )


class IncidenteListaView(AccesoFlotaMixin, ListView):
    model = Incidente
    template_name = "flota/incidente_lista.html"
    context_object_name = "incidentes"

    def get_queryset(self):
        consulta = Incidente.objects.select_related("vehiculo", "conductor")
        gravedad = self.request.GET.get("gravedad")
        if gravedad:
            consulta = consulta.filter(gravedad=gravedad)
        return consulta.order_by("-fecha", "-pk")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["seccion"] = "mantenimientos"
        return contexto


class IncidenteNuevoView(AccesoFlotaMixin, TemplateView):
    template_name = "flota/incidente_nuevo.html"

    def get(self, request, *args, **kwargs):
        return render(
            request,
            self.template_name,
            {"seccion": "mantenimientos", "form": IncidenteForm()},
        )

    def post(self, request, *args, **kwargs):
        form = IncidenteForm(request.POST)
        if form.is_valid():
            incidente = form.save(commit=False)
            incidente.creado_por = request.user
            incidente.save()
            messages.success(request, "Incidente registrado.")
            return redirect("incidentes")
        return render(
            request, self.template_name, {"seccion": "mantenimientos", "form": form}
        )


class AlertasView(AccesoFlotaMixin, TemplateView):
    """Centro de alertas con datos reales de los modelos disponibles en v0.5.

    Se calculan documentos, licencias, servicios abiertos, conductores sin
    vehículo, vehículos sin fotos y —desde la v0.7— novedades críticas sin
    validar. Los mantenimientos llegan en v1.1; mientras tanto no se inventan
    alertas.
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

        # R7 (v0.7): novedad crítica sin validar. Es la única fuente de bloqueo
        # del vehículo desde que la v0.7 migró la regla de la inspección.
        for novedad in (
            Novedad.objects.filter(severidad=Novedad.Severidad.CRITICA)
            .exclude(estado=Novedad.Estado.VALIDADA)
            .select_related("vehiculo")
        ):
            agregar(
                criticas,
                "⚠️",
                "Novedad crítica sin validar",
                f"{novedad.vehiculo.placa} · {novedad.estado} · "
                f"{novedad.reportada_en:%d/%m/%Y %H:%M}",
                novedad.descripcion,
                reverse("novedad_gestion", args=[novedad.pk]),
                "Gestionar novedad",
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

        # Umbrales del contrato §9: 7, 3 y 0 días. Los de 3 y 0 son críticos.
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
            titulo = (
                f"{documento.get_tipo_display()} vence hoy"
                if dias == 0
                else f"{documento.get_tipo_display()} por vencer en {dias} días"
            )
            agregar(
                criticas if dias <= 3 else proximas,
                "🗓️",
                titulo,
                f"{placa} · vence el {documento.vencimiento:%d/%m/%Y} · "
                f"{documento.semaforo_etiqueta}",
                "Renueva el documento y carga el soporte antes de que venza.",
                reverse("documentos:renovar", args=[documento.pk]),
                "Renovar documento",
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
