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
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import FormView, TemplateView

from apps.flota.models import (
    Asignacion,
    Inspeccion,
    PlantillaInspeccion,
    RespuestaItem,
    Servicio,
)
from apps.notificaciones.servicios import notificar_servicio_con_novedad

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
            inspeccion_aprobada = Inspeccion.aprobada_hoy(vehiculo)
            contexto["inspeccion_aprobada"] = inspeccion_aprobada
            contexto["url_inspeccion"] = reverse(
                "inspeccion_rapida", args=[vehiculo.placa]
            )
            contexto["puede_iniciar"] = (
                servicio is None
                and conductor.licencia_vigente
                and not vehiculo.documentos_vencidos.exists()
                and inspeccion_aprobada
            )
            if servicio:
                contexto["motivo_bloqueo"] = (
                    "Ya tienes un servicio en curso: ciérralo antes de iniciar otro."
                )
            elif not conductor.licencia_vigente:
                contexto["motivo_bloqueo"] = (
                    "Tu licencia de conducción venció el "
                    f"{conductor.licencia_vencimiento:%d/%m/%Y}: no puedes iniciar servicio."
                )
            elif vehiculo.documentos_vencidos.exists():
                vencido = vehiculo.documentos_vencidos.first()
                contexto["motivo_bloqueo"] = (
                    f"{vencido.get_tipo_display()} venció el "
                    f"{vencido.vencimiento:%d/%m/%Y}: el vehículo no puede salir."
                )
            elif not inspeccion_aprobada:
                contexto["motivo_bloqueo"] = (
                    "Haz la inspección rápida de hoy antes de iniciar el servicio."
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
        if not Inspeccion.aprobada_hoy(vehiculo):
            # R3: la inspección rápida aprobada del día es obligatoria desde la v0.6.
            messages.error(
                self.request,
                "Haz la inspección rápida de hoy antes de iniciar el servicio.",
            )
            return redirect("inspeccion_rapida", placa=vehiculo.placa)

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
            # v1.0: el contrato §9 pide aviso en la app para el administrador.
            notificar_servicio_con_novedad(servicio)
            messages.warning(
                self.request,
                "Servicio cerrado con novedad. El administrador la revisará.",
            )
        return redirect("mi_servicio")


class InspeccionRapidaView(SoloConductorMixin, View):
    """Inspección rápida del vehículo asignado (v0.6, contrato §5.1).

    El conductor solo ve su propia placa: la ruta lleva la placa, pero se
    comprueba contra su asignación activa. Los respuestas se guardan a medida
    que se envían; la firma con el PIN cierra la inspección y calcula el bloqueo.
    """

    template_name = "servicio/inspeccion_rapida.html"

    def dispatch(self, request, *args, **kwargs):
        conductor = conductor_de(request.user) if request.user.is_authenticated else None
        asignacion = Asignacion.activa_de(conductor) if conductor else None
        if asignacion is None or asignacion.vehiculo.placa != self.kwargs["placa"]:
            if request.user.is_authenticated:
                messages.error(request, "Ese vehículo no está asignado a tu ficha.")
            return redirect("mi_servicio")
        return super().dispatch(request, *args, **kwargs)

    def get_contexto(self, request, errores=None):
        conductor = conductor_de(request.user)
        asignacion = Asignacion.activa_de(conductor)
        vehiculo = asignacion.vehiculo
        contexto = {
            "seccion": "mi_servicio",
            "conductor": conductor,
            "asignacion": asignacion,
            "vehiculo": vehiculo,
            "estados": RespuestaItem.Estado.choices,
            "errores": errores or [],
        }
        plantilla = (
            PlantillaInspeccion.objects.filter(
                activa=True, nivel=PlantillaInspeccion.Nivel.RAPIDA
            )
            .prefetch_related("items")
            .first()
        )
        if plantilla is None or not plantilla.items.exists():
            return contexto

        inspeccion = (
            Inspeccion.objects.filter(
                vehiculo=vehiculo,
                conductor=conductor,
                estado=Inspeccion.Estado.EN_PROGRESO,
                iniciado_en__date=timezone.localdate(),
            )
            .order_by("-pk")
            .first()
        )
        if inspeccion is None:
            inspeccion = Inspeccion.objects.create(
                vehiculo=vehiculo,
                conductor=conductor,
                plantilla=plantilla,
                km=vehiculo.km_actual,
            )
        respuestas = {r.item_id: r for r in inspeccion.respuestas.all()}
        contexto.update(
            {
                "plantilla": plantilla,
                "inspeccion": inspeccion,
                "items": plantilla.items.all(),
                "filas": [
                    {"item": item, "respuesta": respuestas.get(item.pk)}
                    for item in plantilla.items.all()
                ],
            }
        )
        return contexto

    def get(self, request, *args, **kwargs):
        contexto = self.get_contexto(request)
        if contexto.get("plantilla") is None:
            messages.error(request, "Todavía no hay una plantilla de inspección cargada.")
            return redirect("mi_servicio")
        return render(request, self.template_name, contexto)

    def post(self, request, *args, **kwargs):
        contexto = self.get_contexto(request)
        inspeccion = contexto.get("inspeccion")
        items = contexto.get("items", [])
        if inspeccion is None:
            messages.error(request, "No hay una plantilla de inspección cargada.")
            return redirect("mi_servicio")

        errores = []
        estados_validos = {valor for valor, _ in RespuestaItem.Estado.choices}
        for item in items:
            estado = request.POST.get(f"estado-{item.pk}")
            foto = request.FILES.get(f"foto-{item.pk}")
            if estado not in estados_validos:
                errores.append(f"{item.nombre}: elige un estado.")
                continue
            valores = {
                "estado": estado,
                "informe": request.POST.get(f"informe-{item.pk}", ""),
            }
            if foto:
                valores["foto"] = foto
            respuesta, _ = RespuestaItem.objects.update_or_create(
                inspeccion=inspeccion, item=item, defaults=valores
            )
            try:
                respuesta.full_clean()
            except ValidationError as error:
                errores.append(f"{item.nombre}: {error.messages[0]}")

        if not errores:
            try:
                inspeccion.firmar(request.POST.get("firma_pin", ""))
            except ValidationError as error:
                errores.append(error.messages[0])

        if errores:
            contexto["errores"] = errores
            return render(request, self.template_name, contexto)

        messages.success(
            request,
            f"Inspección {inspeccion.resultado} registrada con {inspeccion.vehiculo.placa}.",
        )
        return redirect("mi_servicio")
