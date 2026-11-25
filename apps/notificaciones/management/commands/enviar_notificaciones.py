"""Envía las notificaciones pendientes con reintentos y escalamiento.

Uso (desde la carpeta ``App``)::

    .venv\\Scripts\\python.exe manage.py enviar_notificaciones
    .venv\\Scripts\\python.exe manage.py enviar_notificaciones --resumen

El programador de tareas (Windows, cron o equivalente) debe ejecutar este
comando cada minuto. Con ``--resumen`` genera además el resumen de las 7:00.
Los reintentos se programan con espera creciente; no se duerme dentro del
proceso para no bloquear al servidor.
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.notificaciones.enviadores import ErrorEnvio, enviar
from apps.notificaciones.models import Estado, Notificacion
from apps.notificaciones.servicios import (
    escalar,
    generar_resumen_diario,
    pendientes_de_escalamiento,
    verificar_inspecciones_pendientes,
)


class Command(BaseCommand):
    help = "Procesa la cola de notificaciones, reintentos y escalamiento de críticos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--intentos",
            type=int,
            default=settings.NOTIFICACIONES_INTENTOS,
            help="Número máximo de intentos por canal (por defecto, 3).",
        )
        parser.add_argument(
            "--espera",
            type=int,
            default=settings.NOTIFICACIONES_ESPERA,
            help="Segundos base entre intentos; se duplica en cada fallo.",
        )
        parser.add_argument(
            "--escalar-minutos",
            type=int,
            default=settings.NOTIFICACIONES_ESCALAMIENTO_MINUTOS,
            help="Minutos sin abrir un crítico antes de repetirlo (por defecto, 5).",
        )
        parser.add_argument(
            "--resumen",
            action="store_true",
            help="Genera el resumen diario antes de enviar la cola.",
        )
        parser.add_argument(
            "--mediodia",
            action="store_true",
            help="Genera avisos de inspecciones que siguen en progreso al mediodía.",
        )

    def handle(self, *args, **opciones):
        ahora = timezone.now()
        if opciones["mediodia"]:
            avisos = verificar_inspecciones_pendientes()
            self.stdout.write(f"Inspecciones pendientes: {len(avisos)} aviso(s) nuevo(s).")
        if opciones["resumen"]:
            creadas = generar_resumen_diario()
            self.stdout.write(f"Resumen diario: {len(creadas)} notificación(es) nuevas.")

        pendientes = Notificacion.objects.filter(estado=Estado.PENDIENTE).filter(
            Q(proximo_intento_en__isnull=True) | Q(proximo_intento_en__lte=ahora)
        )
        enviadas = 0
        fallidas = 0
        for notificacion in pendientes:
            try:
                enviar(notificacion)
            except ErrorEnvio as error:
                notificacion.registrar_fallo(
                    error, opciones["espera"], max_intentos=opciones["intentos"]
                )
                fallidas += 1
            else:
                notificacion.marcar_enviada()
                enviadas += 1

        repetidas = 0
        if opciones["escalar_minutos"] > 0:
            for critica in pendientes_de_escalamiento(opciones["escalar_minutos"]):
                repetidas += len(escalar(critica))

        self.stdout.write(
            f"Cola procesada: {enviadas} enviada(s), {fallidas} con error, "
            f"{repetidas} escalada(s)."
        )
