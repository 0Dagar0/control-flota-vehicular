"""Pantallas del conductor: mi servicio, iniciar y cerrar (v0.5, contrato §5.1).

Reglas que se aplican aquí:

- El conductor **no** elige vehículo: usa la asignación hecha por el
  administrador. Si no tiene vehículo asignado, no puede iniciar.
- No se puede iniciar con el vehículo bloqueado por documento vencido (R11) ni
  con la licencia vencida (R21).
- **El cierre siempre se permite**, incluso si el vehículo quedó bloqueado
  durante el recorrido.
- Se puede cerrar sin novedad.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import FormView, TemplateView

from apps.flota.models import Asignacion, Servicio

from .forms import ServicioCerrarForm, ServicioIniciarForm


def conductor_de(usuario):
    """Ficha de conductor del usuario, o ``None`` si no la tiene."""
    return getattr(usuario, "conductor", None)


def actualizar_km(vehiculo, km: int) -> None:
    """Sube el kilometraje del vehículo si el nuevo es mayor (R12)."""
    if km > vehiculo.km_actual:
        vehiculo.km_actual = km
        vehiculo.save(update_fields=["km_actual", "actualizado_en"])


class SoloConductorMixin(LoginRequiredMixin):
    """Estas pantallas son solo para el rol conductor."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.es_conductor:
            messages.warning(request, "Esta sección es del conductor.")
            return redirect("inicio")
        return super().dispatch(request, *args, **kwargs)


class MiServicioView(SoloConductorMixin, TemplateView):
    """Pantalla de inicio del conductor: qué vehículo tiene y qué puede hacer."""

    template_name = "servicio/mi_servicio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        conductor = conductor_de(self.request.user)
        contexto["seccion"] = "mi_servicio"
        contexto["conductor"] = conductor
        contexto["hoy"] = timezone.localdate()
        if conductor is None:
            return contexto

        asignacion = Asignacion.activa_de(conductor)
        servicio = Servicio.en_curso_de(conductor)
        contexto["asignacion"] = asignacion
        contexto["servicio"] = servicio
        contexto["servicios_recientes"] = Servicio.objects.filter(
            conductor=conductor
        ).select_related("vehiculo")[:5]

        if asignacion:
            vehiculo = asignacion.vehiculo
            contexto["vehiculo"] = vehiculo
            contexto["documentos_vencidos"] = list(vehiculo.documentos_vencidos)
            contexto["proximo_documento"] = (
                vehiculo.documentos.order_by("vencimiento").first()
            )
            contexto["puede_iniciar"] = (
                servicio is None
                and conductor.licencia_vigente
                and not vehiculo.documentos_vencidos.exists()
            )
            if not conductor.licencia_vigente:
                contexto["motivo_bloqueo"] = (
                    "Tu licencia de conducción está vencida: no puedes iniciar servicio."
                )
            elif vehiculo.documentos_vencidos.exists():
                contexto["motivo_bloqueo"] = (
                    "El vehículo tiene un documento vencido: no puede salir hasta renovarlo."
                )
        return contexto


class ServicioIniciarView(SoloConductorMixin, FormView):
    form_class = ServicioIniciarForm
    template_name = "servicio/iniciar.html"

    def get_conductor(self):
        return conductor_de(self.request.user)

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            conductor = conductor_de(request.user)
            if conductor is None:
                messages.error(request, "Tu ficha de conductor todavía no existe.")
                return redirect("mi_servicio")
            if Servicio.en_curso_de(conductor):
                messages.warning(request, "Ya tienes un servicio en curso.")
                return redirect("mi_servicio")
        return super().dispatch(request, *args, **kwargs)

    def get_asignacion(self):
        return Asignacion.activa_de(self.get_conductor())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["asignacion"] = self.get_asignacion()
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        asignacion = self.get_asignacion()
        contexto["seccion"] = "mi_servicio"
        contexto["asignacion"] = asignacion
        contexto.update(
            {
                "titulo": "Iniciar servicio",
                "subtitulo": (
                    f"Vehículo {asignacion.vehiculo.placa} · "
                    f"{asignacion.vehiculo.km_actual} km registrados"
                    if asignacion
                    else "No tienes vehículo asignado"
                ),
                "boton": "Iniciar servicio",
                "volver": reverse("mi_servicio"),
            }
        )
        return contexto

    def form_valid(self, form):
        conductor = self.get_conductor()
        asignacion = self.get_asignacion()
        if asignacion is None:
            messages.error(
                self.request, "No tienes vehículo asignado. Pídeselo al administrador."
            )
            return redirect("mi_servicio")
        vehiculo = asignacion.vehiculo
        if not conductor.licencia_vigente:
            messages.error(self.request, "Tu licencia está vencida: no puedes iniciar.")
            return redirect("mi_servicio")
        if vehiculo.documentos_vencidos.exists():
            messages.error(
                self.request, "El vehículo tiene documentos vencidos: no puede salir."
            )
            return redirect("mi_servicio")

        servicio = Servicio.objects.create(
            vehiculo=vehiculo,
            conductor=conductor,
            km_inicial=form.cleaned_data["km_inicial"],
            ruta=form.cleaned_data["ruta"],
        )
        actualizar_km(vehiculo, servicio.km_inicial)
        messages.success(
            self.request, f"Servicio iniciado con {vehiculo.placa}. Buen viaje."
        )
        return redirect("mi_servicio")


class ServicioCerrarView(SoloConductorMixin, FormView):
    form_class = ServicioCerrarForm
    template_name = "servicio/cerrar.html"

    def get_conductor(self):
        return conductor_de(self.request.user)

    def get_servicio(self):
        """Servicio abierto del propio conductor, según el id de la URL."""
        conductor = self.get_conductor()
        if conductor is None:
            return None
        return get_object_or_404(
            Servicio.objects.select_related("vehiculo", "conductor"),
            pk=self.kwargs["pk"],
            conductor=conductor,
            cerrado_en__isnull=True,
        )

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and self.get_servicio() is None:
            messages.info(request, "No tienes ningún servicio en curso.")
            return redirect("mi_servicio")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["servicio"] = self.get_servicio()
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        servicio = self.get_servicio()
        contexto["seccion"] = "mi_servicio"
        contexto["servicio"] = servicio
        contexto.update(
            {
                "titulo": "Cerrar servicio",
                "subtitulo": (
                    f"{servicio.vehiculo.placa} · {servicio.ruta} · "
                    f"iniciado a las {servicio.iniciado_en:%H:%M}"
                    if servicio
                    else ""
                ),
                "boton": "Cerrar servicio",
                "volver": reverse("mi_servicio"),
            }
        )
        return contexto

    def form_valid(self, form):
        servicio = self.get_servicio()
        form.crear_cierre(servicio)
        actualizar_km(servicio.vehiculo, servicio.km_final)
        if servicio.sin_novedad:
            messages.success(
                self.request,
                f"Servicio cerrado: {servicio.km_recorridos} km recorridos, sin novedad.",
            )
        else:
            messages.warning(
                self.request,
                "Servicio cerrado con novedad. El administrador la revisará.",
            )
        return redirect("mi_servicio")
