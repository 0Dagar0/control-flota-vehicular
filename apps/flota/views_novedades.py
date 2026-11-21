"""Vistas de novedades (v0.7): reporte del conductor y bandeja del administrador.

Permisos (contrato §4): el conductor solo reporta y ve las suyas; el
administrador y el superadministrador gestionan la bandeja y los estados.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Case, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView, TemplateView

from apps.servicio.views import SoloConductorMixin, conductor_de

from .forms_novedades import NovedadGestionForm, NovedadReportarForm
from .models import Asignacion, FotoNovedad, Novedad


class NovedadNuevaView(SoloConductorMixin, TemplateView):
    """El conductor reporta una novedad de su vehículo asignado (§5.1)."""

    template_name = "novedades/nueva.html"

    def asignacion(self):
        conductor = conductor_de(self.request.user)
        return Asignacion.activa_de(conductor) if conductor else None

    def contexto(self, form=None, errores=None):
        return {
            "seccion": "novedades",
            "asignacion": self.asignacion(),
            "form": form or NovedadReportarForm(),
            "errores": errores or [],
            "severidades": Novedad.Severidad.choices,
        }

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.contexto())

    def post(self, request, *args, **kwargs):
        asignacion = self.asignacion()
        if asignacion is None:
            messages.error(request, "No tienes vehículo asignado para reportar una novedad.")
            return redirect("mi_servicio")

        form = NovedadReportarForm(request.POST)
        errores = []
        if form.is_valid():
            novedad = form.save(commit=False)
            novedad.vehiculo = asignacion.vehiculo
            novedad.conductor = conductor_de(request.user)
            novedad.origen = Novedad.Origen.REPORTE
            novedad.reportada_por = request.user
            novedad.save()

            # Fotos opcionales: una, varias o ninguna (decisión del dueño).
            for archivo in request.FILES.getlist("fotos"):
                foto = FotoNovedad(
                    novedad=novedad, imagen=archivo, subido_por=request.user
                )
                try:
                    foto.full_clean()
                except ValidationError as error:
                    errores.append(f"{archivo.name}: {error.messages[0]}")
                    continue
                foto.save()

            if not errores:
                messages.success(request, "Novedad reportada. Gracias por avisar.")
                return redirect("mis_novedades")
        return render(request, self.template_name, self.contexto(form, errores))


class NovedadListaView(ListView):
    """Bandeja del administrador con filtros visibles (§5.2)."""

    model = Novedad
    template_name = "novedades/lista.html"
    context_object_name = "novedades"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.es_admin:
            raise PermissionDenied("Esta bandeja es solo para administradores.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        consulta = Novedad.objects.select_related("vehiculo", "conductor__usuario")
        filtros = self.request.GET
        if filtros.get("estado"):
            consulta = consulta.filter(estado=filtros["estado"])
        if filtros.get("severidad"):
            consulta = consulta.filter(severidad=filtros["severidad"])
        if filtros.get("vehiculo", "").strip():
            consulta = consulta.filter(vehiculo__placa__icontains=filtros["vehiculo"].strip())
        if filtros.get("desde"):
            consulta = consulta.filter(reportada_en__date__gte=filtros["desde"])
        if filtros.get("hasta"):
            consulta = consulta.filter(reportada_en__date__lte=filtros["hasta"])

        critica_abierta = Q(
            severidad=Novedad.Severidad.CRITICA, estado=Novedad.Estado.ABIERTA
        )
        return consulta.annotate(
            prioridad=Case(
                When(critica_abierta, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by("prioridad", "-reportada_en")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["seccion"] = "novedades"
        contexto["estados"] = Novedad.Estado.choices
        contexto["severidades"] = Novedad.Severidad.choices
        contexto["filtros"] = self.request.GET
        contexto["total_abiertas"] = Novedad.objects.filter(
            estado=Novedad.Estado.ABIERTA
        ).count()
        contexto["criticas_sin_validar"] = (
            Novedad.objects.filter(severidad=Novedad.Severidad.CRITICA)
            .exclude(estado=Novedad.Estado.VALIDADA)
            .count()
        )
        return contexto


class NovedadGestionView(TemplateView):
    """Gestión de una novedad: estado, descripción e historial (§5.2)."""

    template_name = "novedades/gestion.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.es_admin:
            raise PermissionDenied("Esta gestión es solo para administradores.")
        return super().dispatch(request, *args, **kwargs)

    def get_novedad(self):
        return get_object_or_404(
            Novedad.objects.select_related("vehiculo", "conductor__usuario"),
            pk=self.kwargs["pk"],
        )

    def contexto(self, novedad, form=None):
        return {
            "seccion": "novedades",
            "novedad": novedad,
            "form": form or NovedadGestionForm(
                transiciones=Novedad.TRANSICIONES[novedad.estado]
            ),
            "gestiones": novedad.gestiones.select_related("usuario"),
            "fotos": novedad.fotos.all(),
        }

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.contexto(self.get_novedad()))

    def post(self, request, *args, **kwargs):
        novedad = self.get_novedad()
        form = NovedadGestionForm(
            request.POST, transiciones=Novedad.TRANSICIONES[novedad.estado]
        )
        if form.is_valid():
            try:
                novedad.cambiar_estado(
                    form.cleaned_data["estado"],
                    usuario=request.user,
                    descripcion=form.cleaned_data["descripcion"],
                )
                messages.success(
                    request, f"Novedad actualizada a {novedad.get_estado_display()}."
                )
                return redirect("novedades")
            except ValidationError as error:
                form.add_error("estado", error.messages[0])
        return render(request, self.template_name, self.contexto(novedad, form))


class MisNovedadesView(SoloConductorMixin, ListView):
    """Novedades reportadas por el conductor, con su estado actual."""

    model = Novedad
    template_name = "novedades/mis_novedades.html"
    context_object_name = "novedades"

    def get_queryset(self):
        conductor = conductor_de(self.request.user)
        if conductor is None:
            return Novedad.objects.none()
        return (
            Novedad.objects.filter(conductor=conductor)
            .select_related("vehiculo")
            .order_by("-reportada_en")
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["seccion"] = "novedades"
        return contexto
