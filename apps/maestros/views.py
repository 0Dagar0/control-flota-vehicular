"""Vistas de datos maestros: vehículos, conductores y usuarios.

Permisos según el contrato (§5.2 y §5.3):

- El **administrador** solo consulta la lista de conductores.
- El **superadministrador** crea y edita vehículos, conductores y usuarios, y
  da de baja a un conductor.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, FormView, ListView, UpdateView

from apps.flota.models import Conductor, Vehiculo
from apps.flota.views import AccesoFlotaMixin
from apps.usuarios.models import Usuario

from .forms import (
    AsignarVehiculoForm,
    BajaConductorForm,
    ConductorCompletoForm,
    UsuarioForm,
    VehiculoForm,
)


class SoloSuperadminMixin(LoginRequiredMixin):
    """Solo el superadministrador modifica datos maestros."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.es_superadmin:
            raise PermissionDenied("Solo el superadministrador puede modificar datos maestros.")
        return super().dispatch(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Vehículos
# ---------------------------------------------------------------------------
class VehiculoCrearView(SoloSuperadminMixin, CreateView):
    model = Vehiculo
    form_class = VehiculoForm
    template_name = "formulario.html"
    success_url = reverse_lazy("flota:lista")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            {
                "titulo": "Nuevo vehículo",
                "subtitulo": "Registra un vehículo de la flota",
                "boton": "Guardar vehículo",
                "volver": reverse("flota:lista"),
                "seccion": "vehiculos",
            }
        )
        return contexto

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Vehículo {self.object.placa} guardado.")
        return respuesta


class VehiculoEditarView(SoloSuperadminMixin, UpdateView):
    model = Vehiculo
    form_class = VehiculoForm
    template_name = "formulario.html"
    slug_field = "placa"
    slug_url_kwarg = "placa"

    def get_success_url(self):
        return reverse("flota:detalle", args=[self.object.placa])

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            {
                "titulo": f"Editar {self.object.placa}",
                "subtitulo": "Los cambios quedan registrados en la auditoría del admin",
                "boton": "Guardar cambios",
                "volver": reverse("flota:detalle", args=[self.object.placa]),
                "seccion": "vehiculos",
            }
        )
        return contexto

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Vehículo {self.object.placa} actualizado.")
        return respuesta


# ---------------------------------------------------------------------------
# Conductores
# ---------------------------------------------------------------------------
class ConductorListaView(AccesoFlotaMixin, ListView):
    """Lista de conductores. El administrador la ve, solo el superadmin edita."""

    model = Conductor
    template_name = "maestros/conductor_lista.html"
    context_object_name = "conductores"

    def get_queryset(self):
        return Conductor.objects.select_related("usuario").prefetch_related(
            "asignaciones__vehiculo"
        ).order_by("-activo", "usuario__first_name", "usuario__last_name")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["seccion"] = "conductores"
        contexto["puede_editar"] = self.request.user.es_superadmin
        # Asignar vehículo lo puede hacer el administrador y el superadministrador.
        contexto["puede_asignar"] = self.request.user.es_admin
        return contexto


class ConductorCrearView(SoloSuperadminMixin, FormView):
    form_class = ConductorCompletoForm
    template_name = "formulario.html"
    success_url = reverse_lazy("conductores")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            {
                "titulo": "Nuevo conductor",
                "subtitulo": "Crea el acceso del conductor y su ficha de licencia",
                "boton": "Guardar conductor",
                "volver": reverse("conductores"),
                "seccion": "conductores",
            }
        )
        return contexto

    def form_valid(self, form):
        conductor = form.save()
        messages.success(
            self.request, f"Conductor {conductor} creado con acceso al sistema."
        )
        return redirect(self.success_url)


class ConductorEditarView(SoloSuperadminMixin, FormView):
    form_class = ConductorCompletoForm
    template_name = "formulario.html"

    def get_conductor(self):
        return get_object_or_404(
            Conductor.objects.select_related("usuario"), pk=self.kwargs["pk"]
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["conductor"] = self.get_conductor()
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            {
                "titulo": f"Editar {self.get_conductor()}",
                "subtitulo": "Datos de acceso, licencia y contactos de emergencia",
                "boton": "Guardar cambios",
                "volver": reverse("conductores"),
                "seccion": "conductores",
            }
        )
        return contexto

    def form_valid(self, form):
        conductor = form.save()
        messages.success(self.request, f"Conductor {conductor} actualizado.")
        return redirect("conductores")


class AsignarVehiculoView(AccesoFlotaMixin, FormView):
    """Asigna vehículo a un conductor. Lo puede hacer el admin o el superadmin.

    Es la única forma de que un conductor tenga vehículo: él no se asigna nada.
    """

    form_class = AsignarVehiculoForm
    template_name = "maestros/asignar_vehiculo.html"

    def dispatch(self, request, *args, **kwargs):
        # Un conductor dado de baja no puede recibir un vehículo nuevo.
        if request.user.is_authenticated and not self.get_conductor().activo:
            messages.error(
                request, "Ese conductor está dado de baja: no puede recibir vehículo."
            )
            return redirect("conductores")
        return super().dispatch(request, *args, **kwargs)

    def get_conductor(self):
        return get_object_or_404(
            Conductor.objects.select_related("usuario"), pk=self.kwargs["pk"]
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["conductor"] = self.get_conductor()
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        conductor = self.get_conductor()
        actual = conductor.vehiculo_actual
        contexto.update(
            {
                "titulo": f"Asignar vehículo a {conductor}",
                "subtitulo": (
                    f"Hoy tiene {actual.placa}. Al cambiarlo se cierra la asignación "
                    "anterior con la fecha que indiques."
                    if actual
                    else "Todavía no tiene vehículo asignado."
                ),
                "boton": "Guardar asignación",
                "volver": reverse("conductores"),
                "seccion": "conductores",
                "historial": conductor.asignaciones.select_related("vehiculo")[:5],
            }
        )
        return contexto

    def form_valid(self, form):
        asignacion = form.save(usuario=self.request.user)
        messages.success(
            self.request,
            f"{asignacion.conductor} quedó con el vehículo {asignacion.vehiculo.placa}.",
        )
        return redirect("conductores")


class ConductorBajaView(SoloSuperadminMixin, FormView):
    """R20: la baja marca fecha y motivo; no borra nada del historial."""

    form_class = BajaConductorForm
    template_name = "formulario.html"

    def get_conductor(self):
        return get_object_or_404(
            Conductor.objects.select_related("usuario"), pk=self.kwargs["pk"]
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        conductor = self.get_conductor()
        contexto.update(
            {
                "titulo": f"Dar de baja a {conductor}",
                "subtitulo": "La ficha y sus documentos se conservan en el historial",
                "boton": "Confirmar baja",
                "volver": reverse("conductores"),
                "seccion": "conductores",
            }
        )
        return contexto

    def form_valid(self, form):
        conductor = self.get_conductor()
        if not conductor.activo:
            messages.warning(self.request, f"{conductor} ya estaba dado de baja.")
            return redirect("conductores")
        conductor.activo = False
        conductor.fecha_baja = form.cleaned_data["fecha_baja"]
        conductor.motivo_baja = form.cleaned_data["motivo_baja"]
        conductor.full_clean()
        conductor.save()
        messages.success(self.request, f"{conductor} quedó dado de baja.")
        return redirect("conductores")


# ---------------------------------------------------------------------------
# Usuarios administradores
# ---------------------------------------------------------------------------
class UsuarioListaView(SoloSuperadminMixin, ListView):
    model = Usuario
    template_name = "maestros/usuario_lista.html"
    context_object_name = "usuarios"

    def get_queryset(self):
        return Usuario.objects.order_by("-is_active", "first_name", "last_name")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["seccion"] = "usuarios"
        return contexto


class UsuarioCrearView(SoloSuperadminMixin, FormView):
    form_class = UsuarioForm
    template_name = "formulario.html"
    success_url = reverse_lazy("maestros:usuario_lista")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["actor"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            {
                "titulo": "Nuevo usuario",
                "subtitulo": "Administrador o superadministrador con correo y Telegram",
                "boton": "Crear usuario",
                "volver": reverse("maestros:usuario_lista"),
                "seccion": "usuarios",
            }
        )
        return contexto

    def form_valid(self, form):
        usuario = form.save()
        messages.success(
            self.request, f"Usuario {usuario} creado. Su acceso es con la cédula."
        )
        return redirect(self.success_url)


class UsuarioEditarView(SoloSuperadminMixin, FormView):
    form_class = UsuarioForm
    template_name = "formulario.html"

    def get_usuario(self):
        return get_object_or_404(Usuario, pk=self.kwargs["pk"])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario"] = self.get_usuario()
        kwargs["actor"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            {
                "titulo": f"Editar {self.get_usuario()}",
                "subtitulo": "Si dejas la contraseña vacía, se conserva la actual",
                "boton": "Guardar cambios",
                "volver": reverse("maestros:usuario_lista"),
                "seccion": "usuarios",
            }
        )
        return contexto

    def form_valid(self, form):
        usuario = form.save()
        messages.success(self.request, f"Usuario {usuario} actualizado.")
        return redirect("maestros:usuario_lista")
