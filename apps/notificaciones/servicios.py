"""Reglas de negocio de las notificaciones (v1.0).

Aquí se decide **quién** recibe cada evento, **por qué canales** y con qué
texto. El envío real está en ``enviadores.py`` y la programación en los comandos.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from django.urls import reverse
from django.utils import timezone

from apps.flota.models import Configuracion, Documento, Inspeccion, Mantenimiento, Novedad
from apps.usuarios.models import Usuario

from .models import Canal, Evento, Notificacion, PreferenciaNotificacion

# Canales del contrato §9. Los eventos urgentes usan los cuatro.
CANALES_POR_EVENTO = {
    Evento.NOVEDAD_CRITICA: (Canal.APP, Canal.CORREO, Canal.TELEGRAM, Canal.WEB_PUSH),
    Evento.SOLICITUD_AUTORIZACION: (
        Canal.APP,
        Canal.CORREO,
        Canal.TELEGRAM,
        Canal.WEB_PUSH,
    ),
    Evento.AUTORIZACION_CONCEDIDA: (Canal.APP, Canal.CORREO),
    Evento.DOCUMENTO_PROXIMO: (Canal.APP, Canal.CORREO),
    Evento.INSPECCION_PENDIENTE: (Canal.APP,),
    Evento.SERVICIO_CON_NOVEDAD: (Canal.APP,),
    Evento.MANTENIMIENTO_PROXIMO: (Canal.APP, Canal.CORREO),
    Evento.RESUMEN_DIARIO: (Canal.APP, Canal.CORREO),
    Evento.PRUEBA: (Canal.APP, Canal.CORREO, Canal.TELEGRAM, Canal.WEB_PUSH),
}


def destinatarios_admins():
    """Administradores y superadministradores activos (contrato §9)."""
    return Usuario.objects.filter(
        rol__in=(Usuario.Rol.ADMIN, Usuario.Rol.SUPERADMIN), is_active=True
    )


def destinatarios_superadmins():
    return Usuario.objects.filter(rol=Usuario.Rol.SUPERADMIN, is_active=True)


def crear_notificaciones(
    usuario,
    evento: str,
    titulo: str,
    mensaje: str,
    *,
    canales=None,
    referencia: str = "",
    url: str = "",
    clave: str = "",
):
    """Crea una fila por canal permitido, sin duplicar avisos ya creados.

    La unique constraint de ``Notificacion`` (usuario, evento, canal, clave)
    evita que dos ejecuciones del programador llenen la bandeja de repetidos.
    """

    canales = tuple(canales or CANALES_POR_EVENTO.get(evento, (Canal.APP,)))
    preferencia = PreferenciaNotificacion.para(usuario)
    creadas = []
    for canal in canales:
        if not preferencia.permite(evento, canal):
            continue
        notificacion, creada = Notificacion.objects.get_or_create(
            usuario=usuario,
            evento=evento,
            canal=canal,
            clave=clave,
            defaults={
                "titulo": titulo,
                "mensaje": mensaje,
                "referencia": referencia,
                "url": url,
                "critica": evento in ("novedad_critica", "solicitud_autorizacion"),
            },
        )
        if creada:
            creadas.append(notificacion)
    return creadas


def notificar_novedad(novedad: Novedad):
    """Avisos por novedad crítica y por solicitud de autorización (contrato §9)."""

    creadas = []
    url = reverse("novedad_gestion", args=[novedad.pk])
    referencia = f"novedad:{novedad.pk}"
    if novedad.severidad == Novedad.Severidad.CRITICA:
        for usuario in destinatarios_admins():
            creadas += crear_notificaciones(
                usuario,
                Evento.NOVEDAD_CRITICA,
                f"Novedad crítica en {novedad.vehiculo.placa}",
                f"{novedad.descripcion}\n\nEstado: {novedad.get_estado_display()}.",
                referencia=referencia,
                url=url,
                clave=referencia,
            )
    if novedad.requiere_superadmin:
        for usuario in destinatarios_superadmins():
            creadas += crear_notificaciones(
                usuario,
                Evento.SOLICITUD_AUTORIZACION,
                f"Solicitud de autorización en {novedad.vehiculo.placa}",
                "Una novedad requiere firma del superadministrador para autorizar la salida.",
                referencia=referencia,
                url=reverse("novedad_autorizar", args=[novedad.pk]),
                clave=referencia,
            )
    return creadas


def notificar_autorizacion(novedad: Novedad, autorizado_por=None):
    """Aviso de salida autorizada al conductor y a los administradores."""

    creadas = []
    url = reverse("novedad_gestion", args=[novedad.pk])
    referencia = f"novedad:{novedad.pk}"
    usuarios = list(destinatarios_admins())
    if novedad.conductor_id and novedad.conductor.usuario_id:
        usuarios.append(novedad.conductor.usuario)
    vistos = set()
    for usuario in usuarios:
        if usuario.pk in vistos:
            continue
        vistos.add(usuario.pk)
        creadas += crear_notificaciones(
            usuario,
            Evento.AUTORIZACION_CONCEDIDA,
            f"Salida autorizada en {novedad.vehiculo.placa}",
            "La autorización de salida con falla quedó registrada y firmada.",
            referencia=referencia,
            url=url,
            clave=referencia,
        )
    return creadas


def notificar_servicio_con_novedad(servicio):
    """Aviso a los administradores cuando el conductor cierra con novedad."""

    creadas = []
    for usuario in destinatarios_admins():
        creadas += crear_notificaciones(
            usuario,
            Evento.SERVICIO_CON_NOVEDAD,
            f"Servicio cerrado con novedad en {servicio.vehiculo.placa}",
            servicio.observacion_cierre or "El cierre quedó marcado con novedad.",
            referencia=f"servicio:{servicio.pk}",
            url=reverse("novedades"),
            clave=f"servicio:{servicio.pk}",
        )
    return creadas


def verificar_inspecciones_pendientes(fecha=None, hora=time(12, 0)):
    """Avisa al mediodía si una inspección sigue sin finalizar (contrato §9)."""

    fecha = fecha or timezone.localdate()
    limite = timezone.make_aware(datetime.combine(fecha, hora))
    creadas = []
    pendientes = Inspeccion.objects.filter(
        estado=Inspeccion.Estado.EN_PROGRESO,
        iniciado_en__date__lte=fecha,
        iniciado_en__lt=limite,
    ).select_related("vehiculo")
    for inspeccion in pendientes:
        for usuario in destinatarios_admins():
            creadas += crear_notificaciones(
                usuario,
                Evento.INSPECCION_PENDIENTE,
                f"Inspección pendiente en {inspeccion.vehiculo.placa}",
                "La inspección sigue en progreso después del mediodía.",
                referencia=f"inspeccion:{inspeccion.pk}",
                url=reverse("inspeccion_rapida", args=[inspeccion.vehiculo.placa]),
                clave=f"inspeccion:{inspeccion.pk}:{fecha:%Y-%m-%d}",
            )
    return creadas


def datos_resumen(fecha=None):
    """Reúne lo que va en el resumen de las 7:00 a. m."""

    fecha = fecha or timezone.localdate()
    documentos = (
        Documento.objects.filter(
            vencimiento__gte=fecha,
            vencimiento__lte=fecha + timedelta(days=7),
        )
        .select_related("vehiculo", "conductor__usuario")
        .order_by("vencimiento")
    )
    umbral = Configuracion.obtener().umbral_mantenimiento_km
    mantenimientos = [
        item
        for item in Mantenimiento.objects.select_related("vehiculo").all()
        if item.km_restantes <= umbral
    ]
    inspecciones = Inspeccion.objects.filter(
        estado=Inspeccion.Estado.EN_PROGRESO
    ).select_related("vehiculo", "conductor__usuario")
    return {
        "fecha": fecha,
        "documentos": list(documentos),
        "mantenimientos": mantenimientos,
        "inspecciones": list(inspecciones),
        "umbral": umbral,
    }


def texto_resumen(datos: dict) -> str:
    """Texto único para el correo y la notificación en la app."""

    lineas = [f"Resumen de Mi Flota del {datos['fecha']:%d/%m/%Y}."]
    documentos = datos["documentos"]
    lineas.append(f"Documentos a 7, 3 y 0 días: {len(documentos)}.")
    for documento in documentos[:10]:
        dueno = documento.vehiculo.placa if documento.vehiculo_id else (
            documento.conductor.usuario.get_full_name()
            if documento.conductor_id
            else "sin dueño"
        )
        lineas.append(
            f"- {documento.get_tipo_display()} de {dueno}: "
            f"{documento.dias_para_vencer} día(s) ({documento.vencimiento:%d/%m/%Y})."
        )
    mantenimientos = datos["mantenimientos"]
    lineas.append(
        f"\nMantenimientos bajo el umbral de {datos['umbral']} km: "
        f"{len(mantenimientos)}."
    )
    for item in mantenimientos[:10]:
        lineas.append(
            f"- {item.vehiculo.placa}: faltan {item.km_restantes} km para "
            f"{item.servicio}."
        )
    inspecciones = datos["inspecciones"]
    lineas.append(f"\nInspecciones pendientes: {len(inspecciones)}.")
    return "\n".join(lineas)


def generar_resumen_diario(fecha=None):
    """Crea el resumen de las 7:00 para administradores y superadministradores."""

    fecha = fecha or timezone.localdate()
    datos = datos_resumen(fecha)
    texto = texto_resumen(datos)
    creadas = []
    for usuario in destinatarios_admins():
        creadas += crear_notificaciones(
            usuario,
            Evento.RESUMEN_DIARIO,
            f"Resumen diario del {fecha:%d/%m/%Y}",
            texto,
            referencia=f"resumen:{fecha:%Y-%m-%d}",
            url=reverse("notificaciones:resumen_diario"),
            clave=f"resumen:{fecha:%Y-%m-%d}",
        )
    return creadas


def escalar(notificacion: Notificacion):
    """Repite un crítico por los 4 canales si nadie lo abrió en 5 minutos."""

    creadas = crear_notificaciones(
        notificacion.usuario,
        notificacion.evento,
        f"REGRESO: {notificacion.titulo}",
        notificacion.mensaje,
        canales=(Canal.APP, Canal.CORREO, Canal.TELEGRAM, Canal.WEB_PUSH),
        referencia=notificacion.referencia,
        url=notificacion.url,
        clave=f"escala:{notificacion.pk}",
    )
    notificacion.escalada_en = timezone.now()
    notificacion.save(update_fields=["escalada_en"])
    return creadas


def pendientes_de_escalamiento(minutos: int):
    """Críticos enviados, sin leer y con más de ``minutos`` sin abrir."""

    limite = timezone.now() - timedelta(minutes=minutos)
    return Notificacion.objects.filter(
        evento__in=("novedad_critica", "solicitud_autorizacion"),
        estado="enviada",
        leida_en__isnull=True,
        escalada_en__isnull=True,
        creado_en__lte=limite,
    )
