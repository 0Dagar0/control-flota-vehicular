"""Pantallas de la bandeja, preferencias y estado de canales (v1.0)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import DetailView, FormView, ListView, TemplateView, View

from .forms import PreferenciaForm
from .models import Canal, Estado, Notificacion, PreferenciaNotificacion, SuscripcionPush
from .servicios import datos_resumen, texto_resumen


class BandejaView(LoginRequiredMixin, ListView):
    """Bandeja del usuario con filtros y contador de sin leer."""

    model = Notificacion
    template_name = "notificaciones/lista.html"
    context_object_name = "notificaciones"
    paginate_by = 20

    def get_queryset(self):
        consulta = Notificacion.objects.filter(usuario=self.request.user)
        filtros = self.request.GET
        if filtros.get("q", "").strip():
            texto = filtros["q"].strip()
            consulta = consulta.filter(
                models_q(texto)
            )
        if filtros.get("canal"):
            consulta = consulta.filter(canal=filtros["canal"])
        if filtros.get("estado"):
            consulta = consulta.filter(estado=filtros["estado"])
        if filtros.get("evento"):
            consulta = consulta.filter(evento=filtros["evento"])
        if filtros.get("desde"):
            consulta = consulta.filter(creado_en__date__gte=filtros["desde"])
        if filtros.get("hasta"):
            consulta = consulta.filter(creado_en__date__lte=filtros["hasta"])
        return consulta.select_related("usuario")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["seccion"] = "notificaciones"
        contexto["filtros"] = self.request.GET
        contexto["canales"] = Canal.choices
        contexto["estados"] = Estado.choices
        contexto["eventos"] = Notificacion._meta.get_field("evento").choices
        contexto["sin_leer"] = Notificacion.objects.filter(
            usuario=self.request.user, leida_en__isnull=True
        ).count()
        return contexto


def models_q(texto):
    """Expresión OR para el buscador (separada para mantener la vista limpia)."""

    from django.db.models import Q

    return Q(titulo__icontains=texto) | Q(mensaje__icontains=texto)


class MarcarTodasLeidasView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        actualizadas = Notificacion.objects.filter(
            usuario=request.user, leida_en__isnull=True
        ).update(estado=Estado.LEIDA, leida_en=timezone.now(), proximo_intento_en=None)
        messages.success(request, f"{actualizadas} notificación(es) marcadas como leídas.")
        return HttpResponse(status=204, headers={"HX-Refresh": "true"})


class NotificacionDetalleView(LoginRequiredMixin, DetailView):
    model = Notificacion
    template_name = "notificaciones/detalle.html"
    context_object_name = "notificacion"

    def get_queryset(self):
        return Notificacion.objects.filter(usuario=self.request.user)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["seccion"] = "notificaciones"
        # Una línea de tiempo con el estado de los 4 canales del mismo evento.
        contexto["canales"] = [
            {
                "nombre": nombre,
                "notificacion": Notificacion.objects.filter(
                    usuario=self.request.user,
                    evento=self.object.evento,
                    canal=clave,
                    referencia=self.object.referencia,
                )
                .order_by("-creado_en")
                .first(),
            }
            for clave, nombre in Canal.choices
        ]
        contexto["escalamiento_minutos"] = settings.NOTIFICACIONES_ESCALAMIENTO_MINUTOS
        return contexto


class MarcarLeidaView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        notificacion = Notificacion.objects.filter(
            pk=kwargs["pk"], usuario=request.user
        ).first()
        if notificacion is not None and notificacion.leida_en is None:
            notificacion.marcar_leida()
            messages.success(request, "Notificación marcada como leída.")
        return HttpResponse(status=204, headers={"HX-Refresh": "true"})


class PreferenciasView(LoginRequiredMixin, FormView):
    template_name = "notificaciones/preferencias.html"
    form_class = PreferenciaForm
    success_url = reverse_lazy("notificaciones:preferencias")

    def get_form_kwargs(self):
        argumentos = super().get_form_kwargs()
        argumentos["instance"] = PreferenciaNotificacion.para(self.request.user)
        return argumentos

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["seccion"] = "notificaciones"
        contexto["vapid_public_key"] = settings.VAPID_PUBLIC_KEY
        contexto["chat_id"] = self.request.user.telegram_chat_id
        contexto["correo"] = self.request.user.email
        return contexto

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        form.save()
        messages.success(self.request, "Preferencias guardadas. No se envió ninguna prueba.")
        return super().form_valid(form)


class CanalesView(LoginRequiredMixin, TemplateView):
    template_name = "notificaciones/canales.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.es_superadmin:
            raise PermissionDenied("El estado de los canales es solo para superadministradores.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["seccion"] = "notificaciones"
        token = settings.TELEGRAM_BOT_TOKEN.strip()
        publica = settings.VAPID_PUBLIC_KEY.strip()
        huella = ""
        if publica:
            huella = hashlib.sha256(publica.encode("utf-8")).hexdigest()[:16]
        contexto["canales"] = [
            {
                "nombre": "Correo (SMTP)",
                "configurado": bool(settings.MAILERS.get("default", {})
                                    .get("BACKEND", "").endswith("smtp.EmailBackend")),
                "detalle": f"Usuario: {self._enmascarar(settings.CORREO_REMITENTE)}",
                "nota": "Contraseña de aplicación guardada fuera del código.",
            },
            {
                "nombre": "Telegram",
                "configurado": bool(token) and not token.startswith("<"),
                "detalle": (
                    "Token: "
                    + ("••••••••" if token and not token.startswith("<") else "sin configurar")
                ),
                "nota": "El token solo vive en .env; se revoca con /revoke si se filtra.",
            },
            {
                "nombre": "Web Push (VAPID)",
                "configurado": bool(publica and settings.VAPID_PRIVATE_KEY_B64),
                "detalle": f"Clave pública: {huella or 'sin configurar'} (huella SHA-256)",
                "nota": (
                    "La clave privada nunca se muestra; cambiarla obliga a suscribirse de nuevo."
                ),
            },
        ]
        contexto["ultimos"] = Notificacion.objects.exclude(canal=Canal.APP).order_by(
            "-enviado_en"
        )[:6]
        return contexto

    @staticmethod
    def _enmascarar(texto: str) -> str:
        if not texto:
            return "sin configurar"
        return (texto[:2] + "••••••" + texto[-2:]) if len(texto) > 5 else "••••••"


class ResumenDiarioView(LoginRequiredMixin, TemplateView):
    template_name = "notificaciones/resumen_diario.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["seccion"] = "notificaciones"
        datos = datos_resumen()
        contexto["datos"] = datos
        contexto["texto"] = texto_resumen(datos)
        return contexto


class SuscribirPushView(LoginRequiredMixin, View):
    """Guarda la suscripción que envía el navegador (sin secretos en la URL)."""

    def post(self, request, *args, **kwargs):
        try:
            cuerpo = json.loads(request.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({"ok": False, "error": "JSON inválido."}, status=400)
        endpoint = str(cuerpo.get("endpoint", "")).strip()
        claves = cuerpo.get("keys") or {}
        p256dh = str(claves.get("p256dh", "")).strip()
        auth = str(claves.get("auth", "")).strip()
        if not endpoint.startswith("https://") or not p256dh or not auth:
            return JsonResponse(
                {"ok": False, "error": "Faltan endpoint o claves de la suscripción."},
                status=400,
            )
        SuscripcionPush.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "usuario": request.user,
                "p256dh": p256dh[:200],
                "auth": auth[:200],
                "activa": True,
            },
        )
        return JsonResponse({"ok": True})


def service_worker(request):
    """Sirve ``sw.js`` desde la raíz para que su ámbito sea todo el sitio."""

    ruta = Path(settings.BASE_DIR) / "static" / "sw.js"
    return HttpResponse(
        ruta.read_text(encoding="utf-8"),
        content_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )
