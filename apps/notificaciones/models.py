"""Modelos de la v1.0: notificaciones, preferencias y suscripciones Web Push.

Cada aviso se guarda **una vez por usuario, evento y canal** (``Notificacion``).
Así la bandeja sirve también como historial: se ve cuándo se envió, cuántos
intentos hicieron falta y qué error hubo, sin borrar nunca el registro.

Reglas del proyecto aplicadas aquí (``docs/DOCUMENTO_MAESTRO.md`` §9):

- **R15:** los eventos críticos no se pueden silenciar.
- Escalamiento: un crítico se repite por los 4 canales a los 5 minutos si
  nadie lo ha abierto.
- Reintentos: 3 por canal con espera creciente; el error queda registrado.
"""

from datetime import time, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Evento(models.TextChoices):
    """Los siete eventos del contrato (§9) más el resumen y la prueba."""

    NOVEDAD_CRITICA = "novedad_critica", "Novedad crítica"
    SOLICITUD_AUTORIZACION = "solicitud_autorizacion", "Solicitud de autorización"
    AUTORIZACION_CONCEDIDA = "autorizacion_concedida", "Autorización concedida"
    DOCUMENTO_PROXIMO = "documento_proximo", "Documento a 7, 3 y 0 días"
    INSPECCION_PENDIENTE = "inspeccion_pendiente", "Inspección no realizada"
    SERVICIO_CON_NOVEDAD = "servicio_con_novedad", "Servicio cerrado con novedad"
    MANTENIMIENTO_PROXIMO = "mantenimiento_proximo", "Mantenimiento próximo"
    RESUMEN_DIARIO = "resumen_diario", "Resumen diario"
    PRUEBA = "prueba", "Prueba de canal"


# R15: estos dos eventos nunca se pueden desactivar desde las preferencias.
CRITICOS = frozenset({Evento.NOVEDAD_CRITICA, Evento.SOLICITUD_AUTORIZACION})


class Canal(models.TextChoices):
    APP = "app", "App"
    CORREO = "correo", "Correo"
    TELEGRAM = "telegram", "Telegram"
    WEB_PUSH = "web_push", "Web Push"


class Estado(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    ENVIADA = "enviada", "Enviada"
    LEIDA = "leida", "Leída"
    FALLIDA = "fallida", "Fallida"


class Notificacion(models.Model):
    """Un aviso para un usuario por un canal concreto."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuario",
        on_delete=models.PROTECT,
        related_name="notificaciones",
    )
    evento = models.CharField("evento", max_length=30, choices=Evento.choices)
    canal = models.CharField("canal", max_length=10, choices=Canal.choices)
    estado = models.CharField(
        "estado", max_length=10, choices=Estado.choices, default=Estado.PENDIENTE
    )
    titulo = models.CharField("título", max_length=180)
    mensaje = models.TextField("mensaje")
    url = models.CharField("enlace al registro", max_length=200, blank=True)
    referencia = models.CharField("registro de origen", max_length=120, blank=True)
    clave = models.CharField(
        "clave de agrupación",
        max_length=100,
        blank=True,
        help_text="Evita crear dos veces el mismo aviso (por ejemplo, el resumen de un día).",
    )
    critica = models.BooleanField("crítica", default=False)
    intentos = models.PositiveSmallIntegerField("intentos", default=0)
    error = models.TextField("último error", blank=True)
    creado_en = models.DateTimeField("creado en", default=timezone.now)
    enviado_en = models.DateTimeField("enviado en", null=True, blank=True)
    leida_en = models.DateTimeField("leída en", null=True, blank=True)
    proximo_intento_en = models.DateTimeField("próximo intento", null=True, blank=True)
    escalada_en = models.DateTimeField("escalada en", null=True, blank=True)

    class Meta:
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"
        ordering = ["-creado_en", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "evento", "canal", "clave"],
                name="notificacion_unica_por_usuario_evento_canal_clave",
            )
        ]
        indexes = [
            models.Index(
                fields=["estado", "proximo_intento_en"], name="notif_estado_proximo_idx"
            )
        ]

    def __str__(self):
        return f"{self.get_evento_display()} · {self.get_canal_display()} · {self.usuario}"

    @property
    def es_critica(self) -> bool:
        """R15: los eventos críticos lo son aunque la fila se haya creado a mano."""
        return self.critica or self.evento in CRITICOS

    @property
    def sin_leer(self) -> bool:
        return self.leida_en is None

    def marcar_enviada(self) -> None:
        self.estado = Estado.ENVIADA
        self.enviado_en = timezone.now()
        self.proximo_intento_en = None
        self.error = ""
        self.save(
            update_fields=["estado", "enviado_en", "proximo_intento_en", "error"]
        )

    def marcar_leida(self) -> None:
        self.estado = Estado.LEIDA
        self.leida_en = timezone.now()
        self.proximo_intento_en = None
        self.save(update_fields=["estado", "leida_en", "proximo_intento_en"])

    def registrar_fallo(
        self, error: str, espera_segundos: int, max_intentos: int = 3
    ) -> None:
        """Guarda el error y programa el siguiente intento (espera creciente)."""
        self.intentos += 1
        self.error = str(error)[:1000]
        if self.intentos >= max_intentos:
            self.estado = Estado.FALLIDA
            self.proximo_intento_en = None
            campos = ["intentos", "error", "estado", "proximo_intento_en"]
        else:
            self.proximo_intento_en = timezone.now() + timedelta(
                seconds=espera_segundos * (2 ** (self.intentos - 1))
            )
            campos = ["intentos", "error", "proximo_intento_en"]
        self.save(update_fields=campos)


class PreferenciaNotificacion(models.Model):
    """Canales que cada usuario quiere recibir. La app siempre está activa."""

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="usuario",
        on_delete=models.CASCADE,
        related_name="preferencia_notificaciones",
    )
    correo = models.BooleanField("correo", default=True)
    telegram = models.BooleanField("Telegram", default=True)
    web_push = models.BooleanField("Web Push", default=True)
    resumen_diario = models.BooleanField("resumen diario", default=True)
    hora_resumen = models.TimeField("hora del resumen", default=time(7, 0))

    class Meta:
        verbose_name = "preferencia de notificaciones"
        verbose_name_plural = "preferencias de notificaciones"

    def __str__(self):
        return f"Preferencias de {self.usuario}"

    def permite(self, evento: str, canal: str) -> bool:
        """R15: la app y los eventos críticos nunca se pueden silenciar."""
        if canal == Canal.APP or evento in CRITICOS:
            return True
        return {
            Canal.CORREO: self.correo,
            Canal.TELEGRAM: self.telegram,
            Canal.WEB_PUSH: self.web_push,
        }.get(canal, True)

    @classmethod
    def para(cls, usuario) -> "PreferenciaNotificacion":
        """Devuelve la preferencia existente o una con valores por defecto."""
        try:
            return usuario.preferencia_notificaciones
        except cls.DoesNotExist:
            return cls(usuario=usuario)


class SuscripcionPush(models.Model):
    """Endpoint de un navegador autorizado para recibir Web Push."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuario",
        on_delete=models.CASCADE,
        related_name="suscripciones_push",
    )
    endpoint = models.TextField("endpoint", unique=True)
    p256dh = models.CharField("clave p256dh", max_length=200)
    auth = models.CharField("clave auth", max_length=200)
    activa = models.BooleanField("activa", default=True)
    creado_en = models.DateTimeField("creado en", default=timezone.now)

    class Meta:
        verbose_name = "suscripción Web Push"
        verbose_name_plural = "suscripciones Web Push"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"Push de {self.usuario} · {self.endpoint[:40]}…"
