"""Modelos de la flota: vehículo, conductor, documento y configuración.

Reglas del proyecto que se aplican aquí (``docs/DOCUMENTO_MAESTRO.md``, sección 7):

- **R11** un documento vencido del **vehículo** lo bloquea.
- **R12** el kilometraje nunca puede disminuir.
- **R19** todo documento debería tener soporte digital (foto o PDF); puede
  registrarse sin él y queda «pendiente» hasta que se suba.
- **R20** la baja de un conductor no borra nada: marca fechas y motivo.
- **R21** la licencia vencida inhabilita al **conductor**, no al vehículo.
- **R3/R5/R6/R7** (v0.6) la inspección se firma con la contraseña del conductor, exige
  foto en los ítems con novedad y bloquea si un ítem crítico tiene novedad.

Los estados ``EN_SERVICIO``, ``BLOQUEADO_NOVEDAD`` y ``EN_MANTENIMIENTO`` se
activarán en las versiones que crean servicios, novedades y mantenimientos; por
ahora solo se calculan los que dependen de los documentos y de la baja.
"""

import hashlib
from datetime import date
from pathlib import Path

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

PLACA_VALIDA = RegexValidator(
    regex=r"^[A-Z]{3}[0-9]{3}$",
    message="La placa debe tener 3 letras y 3 dígitos (por ejemplo, ABC123).",
)


class Configuracion(models.Model):
    """Parámetros del sistema. Debe existir un solo registro."""

    umbral_mantenimiento_km = models.PositiveIntegerField(
        "aviso de mantenimiento (km)", default=500
    )
    minutos_autorizacion = models.PositiveSmallIntegerField("minutos para autorizar", default=15)
    dias_aviso_documento = models.PositiveSmallIntegerField(
        "días de aviso de documentos", default=30
    )
    actualizado_en = models.DateTimeField("actualizado en", auto_now=True)

    class Meta:
        verbose_name = "configuración"
        verbose_name_plural = "configuración"

    def __str__(self):
        return "Configuración del sistema"

    def save(self, *args, **kwargs):
        # Un único registro: siempre con la clave primaria 1.
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def obtener(cls):
        """Devuelve la configuración, creándola con los valores por defecto."""
        configuracion, _ = cls.objects.get_or_create(pk=1)
        return configuracion


class Vehiculo(models.Model):
    """Vehículo de la flota. El estado es calculado, no editable."""

    class Estado(models.TextChoices):
        OPERATIVO = "operativo", "Operativo"
        EN_SERVICIO = "en_servicio", "En servicio"
        BLOQUEADO_NOVEDAD = "bloqueado_novedad", "Bloqueado por novedad"
        BLOQUEADO_DOCUMENTO = "bloqueado_documento", "Bloqueado por documento"
        EN_MANTENIMIENTO = "en_mantenimiento", "En mantenimiento"
        FUERA_DE_SERVICIO = "fuera_de_servicio", "Fuera de servicio"

    class Combustible(models.TextChoices):
        GASOLINA = "gasolina", "Gasolina"
        DIESEL = "diesel", "Diésel"
        GAS = "gas", "Gas"
        ELECTRICO = "electrico", "Eléctrico"
        HIBRIDO = "hibrido", "Híbrido"

    placa = models.CharField("placa", max_length=6, unique=True, validators=[PLACA_VALIDA])
    marca = models.CharField("marca", max_length=40)
    referencia = models.CharField("referencia", max_length=60)
    modelo = models.PositiveSmallIntegerField("modelo (año)")
    tipo_carroceria = models.CharField("tipo de carrocería", max_length=40, blank=True)
    vin = models.CharField("VIN", max_length=17, blank=True)
    motor = models.CharField("número de motor", max_length=30, blank=True)
    combustible = models.CharField(
        "combustible", max_length=20, choices=Combustible.choices, default=Combustible.GASOLINA
    )
    km_actual = models.PositiveIntegerField("kilometraje actual", default=0)
    propietario = models.CharField("propietario", max_length=80, blank=True)
    activo = models.BooleanField("activo", default=True)

    creado_en = models.DateTimeField("creado en", auto_now_add=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="creado por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    actualizado_en = models.DateTimeField("actualizado en", auto_now=True)

    class Meta:
        verbose_name = "vehículo"
        verbose_name_plural = "vehículos"
        ordering = ["placa"]

    def __str__(self):
        return f"{self.placa} · {self.marca} {self.referencia} {self.modelo}"

    def save(self, *args, **kwargs):
        self.placa = (self.placa or "").strip().upper()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        self.placa = (self.placa or "").strip().upper()
        anio_maximo = timezone.localdate().year + 1
        if self.modelo and not 1950 <= self.modelo <= anio_maximo:
            raise ValidationError({"modelo": f"El modelo debe estar entre 1950 y {anio_maximo}."})
        # R12: el kilometraje nunca puede disminuir.
        if self.pk:
            anterior = (
                Vehiculo.objects.filter(pk=self.pk).values_list("km_actual", flat=True).first()
            )
            if anterior is not None and self.km_actual < anterior:
                raise ValidationError(
                    {"km_actual": "El kilometraje no puede ser menor al último registrado."}
                )

    @property
    def documentos_vehiculo(self):
        """Documentos propios del vehículo (excluye licencias de conducción)."""
        return self.documentos.exclude(tipo=Documento.Tipo.LICENCIA)

    @property
    def documentos_vencidos(self):
        return self.documentos_vehiculo.filter(vencimiento__lt=timezone.localdate())

    @property
    def estado(self) -> str:
        """Estado calculado (R11 y, desde la v0.6, bloqueo por inspección crítica)."""
        if not self.activo:
            return self.Estado.FUERA_DE_SERVICIO
        if self.documentos_vencidos.exists():
            return self.Estado.BLOQUEADO_DOCUMENTO
        # R7 (v0.7, opción A): solo la novedad crítica sin validar bloquea.
        # La inspección ya no es fuente de bloqueo: al firmarse como bloqueada
        # crea la novedad, que pasa a ser la única fuente de verdad.
        if self.novedades.filter(severidad="critica").exclude(estado="VALIDADA").exists():
            return self.Estado.BLOQUEADO_NOVEDAD
        return self.Estado.OPERATIVO

    @property
    def estado_etiqueta(self) -> str:
        """Nombre legible del estado, para mostrarlo en las plantillas."""
        return self.Estado(self.estado).label


def ruta_foto_vehiculo(instancia: "FotoVehiculo", nombre_original: str) -> str:
    """Nombre descriptivo del archivo: ``fotos/vehiculos/2026/11/ABC123-frontal.jpg``."""
    hoy = timezone.localdate()
    extension = Path(nombre_original).suffix.lower() or ".jpg"
    return f"fotos/vehiculos/{hoy:%Y/%m}/{instancia.vehiculo.placa}-{instancia.tipo}{extension}"


def validar_peso_imagen(archivo):
    """Rechaza imágenes de más de 8 MB para no llenar el disco."""
    limite = 8 * 1024 * 1024
    if archivo.size > limite:
        raise ValidationError("La imagen no puede pesar más de 8 MB.")


def validar_imagen_real(archivo):
    """Comprueba que el archivo sea de verdad una imagen y no un PDF renombrado."""
    try:
        with Image.open(archivo) as imagen:
            imagen.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
        raise ValidationError("El archivo no es una imagen válida (JPG, PNG o WEBP).") from error
    finally:
        archivo.seek(0)


class FotoVehiculo(models.Model):
    """Foto del vehículo identificada por el ángulo o la parte que muestra.

    Las fotos de documentos (licencia de tránsito, SOAT, tecnomecánica) no van
    aquí: cada documento guarda su propio soporte en ``Documento.soporte`` (R19).
    """

    class Tipo(models.TextChoices):
        FRONTAL = "frontal", "Frontal"
        TRASERA = "trasera", "Parte trasera"
        LATERAL_IZQUIERDO = "lateral_izquierdo", "Lateral izquierdo"
        LATERAL_DERECHO = "lateral_derecho", "Lateral derecho"
        INTERIOR_CABINA = "interior_cabina", "Interior / cabina"
        TABLERO_KILOMETRAJE = "tablero_kilometraje", "Tablero (kilometraje)"

    vehiculo = models.ForeignKey(
        Vehiculo,
        verbose_name="vehículo",
        on_delete=models.CASCADE,
        related_name="fotos",
    )
    tipo = models.CharField("tipo de foto", max_length=20, choices=Tipo.choices)
    imagen = models.ImageField(
        "imagen",
        upload_to=ruta_foto_vehiculo,
        max_length=255,
        validators=[validar_peso_imagen, validar_imagen_real],
    )
    descripcion = models.CharField("descripción", max_length=150, blank=True)

    subida_en = models.DateTimeField("subida en", auto_now_add=True)
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="subida por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "foto del vehículo"
        verbose_name_plural = "fotos del vehículo"
        ordering = ["vehiculo__placa", "tipo", "-subida_en"]

    def __str__(self):
        return f"{self.vehiculo.placa} · {self.get_tipo_display()}"

    @property
    def nombre_archivo(self) -> str:
        return Path(self.imagen.name).name


class Conductor(models.Model):
    """Conductor de la flota, asociado a un usuario con rol «conductor»."""

    class CategoriaLicencia(models.TextChoices):
        A2 = "a2", "A2"
        B1 = "b1", "B1"
        B2 = "b2", "B2"
        C1 = "c1", "C1"
        C2 = "c2", "C2"
        C3 = "c3", "C3"

    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        INACTIVO = "inactivo", "Inactivo (dado de baja)"
        NO_HABILITADO = "no_habilitado", "No habilitado (licencia)"

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="usuario",
        on_delete=models.PROTECT,
        related_name="conductor",
        limit_choices_to={"rol": "conductor"},
    )
    licencia_categoria = models.CharField(
        "categoría de la licencia",
        max_length=2,
        choices=CategoriaLicencia.choices,
        default=CategoriaLicencia.B2,
    )
    licencia_vencimiento = models.DateField("vencimiento de la licencia")
    contacto_emergencia_nombre = models.CharField(
        "contacto de emergencia", max_length=80, blank=True
    )
    contacto_emergencia_telefono = models.CharField(
        "teléfono de emergencia", max_length=20, blank=True
    )

    activo = models.BooleanField("activo", default=True)
    fecha_baja = models.DateField("fecha de baja", null=True, blank=True)
    motivo_baja = models.CharField("motivo de la baja", max_length=200, blank=True)

    creado_en = models.DateTimeField("creado en", auto_now_add=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="creado por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    actualizado_en = models.DateTimeField("actualizado en", auto_now=True)

    class Meta:
        verbose_name = "conductor"
        verbose_name_plural = "conductores"
        ordering = ["usuario__first_name", "usuario__last_name"]

    def __str__(self):
        return f"{self.usuario.get_full_name() or self.usuario.documento}"

    def clean(self):
        super().clean()
        # R20: una baja siempre lleva fecha y un motivo; un activo no puede tener baja.
        if self.fecha_baja and self.activo:
            raise ValidationError(
                {"fecha_baja": "Si registra una fecha de baja, desmarque «activo»."}
            )
        if not self.activo and not self.fecha_baja:
            raise ValidationError({"fecha_baja": "Indique la fecha en que se dio de baja."})
        if not self.activo and not self.motivo_baja:
            raise ValidationError({"motivo_baja": "Indique el motivo de la baja."})

    @property
    def licencia_vigente(self) -> bool:
        return self.licencia_vencimiento >= timezone.localdate()

    @property
    def dias_para_vencer_licencia(self) -> int:
        return (self.licencia_vencimiento - timezone.localdate()).days

    @property
    def estado(self) -> str:
        """Estado calculado (R20 y R21)."""
        if not self.activo:
            return self.Estado.INACTIVO
        if not self.licencia_vigente:
            return self.Estado.NO_HABILITADO
        return self.Estado.ACTIVO

    @property
    def vehiculo_actual(self):
        """Vehículo asignado hoy, o ``None`` (la asignación la hace el admin)."""
        asignacion = (
            self.asignaciones.filter(fecha_fin__isnull=True)
            .select_related("vehiculo")
            .first()
        )
        return asignacion.vehiculo if asignacion else None


class Documento(models.Model):
    """Documento del vehículo o del conductor, con su soporte digital.

    R19: el soporte (foto o PDF) puede subirse después; mientras no esté, el
    documento se muestra como «soporte pendiente».
    """

    class Tipo(models.TextChoices):
        SOAT = "soat", "SOAT"
        TECNOMECANICA = "tecnomecanica", "Revisión técnico-mecánica"
        POLIZA = "poliza", "Póliza todo riesgo"
        LICENCIA = "licencia", "Licencia de conducción"

    TIPOS_VEHICULO = (Tipo.SOAT, Tipo.TECNOMECANICA, Tipo.POLIZA)
    TIPOS_CONDUCTOR = (Tipo.LICENCIA,)

    tipo = models.CharField("tipo", max_length=20, choices=Tipo.choices)
    vehiculo = models.ForeignKey(
        Vehiculo,
        verbose_name="vehículo",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="documentos",
    )
    conductor = models.ForeignKey(
        Conductor,
        verbose_name="conductor",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="documentos",
    )
    entidad = models.CharField("entidad o aseguradora", max_length=80, blank=True)
    numero = models.CharField("número", max_length=40, blank=True)
    vencimiento = models.DateField("vencimiento")
    soporte = models.FileField(
        "soporte (foto o PDF)",
        upload_to="documentos/%Y/%m/",
        max_length=255,
        blank=True,
    )

    creado_en = models.DateTimeField("creado en", auto_now_add=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="creado por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    actualizado_en = models.DateTimeField("actualizado en", auto_now=True)

    class Meta:
        verbose_name = "documento"
        verbose_name_plural = "documentos"
        ordering = ["vencimiento"]

    def __str__(self):
        dueño = self.vehiculo.placa if self.vehiculo_id else str(self.conductor)
        return f"{self.get_tipo_display()} · {dueño} · vence {self.vencimiento:%d/%m/%Y}"

    def clean(self):
        super().clean()
        # El documento pertenece a un vehículo o a un conductor, nunca a los dos.
        if self.vehiculo_id and self.conductor_id:
            raise ValidationError(
                "Un documento pertenece a un vehículo o a un conductor, no a los dos."
            )
        if not self.vehiculo_id and not self.conductor_id:
            raise ValidationError("Seleccione el vehículo o el conductor del documento.")
        if self.tipo in self.TIPOS_CONDUCTOR and not self.conductor_id:
            raise ValidationError({"conductor": "La licencia es un documento del conductor."})
        if self.tipo in self.TIPOS_VEHICULO and not self.vehiculo_id:
            raise ValidationError({"vehiculo": "Este tipo de documento pertenece a un vehículo."})

    @property
    def tiene_soporte(self) -> bool:
        return bool(self.soporte)

    @property
    def estado_soporte(self) -> str:
        """R19: el soporte puede quedar pendiente y subirse después."""
        return "Cargado" if self.tiene_soporte else "Pendiente"

    @property
    def dias_para_vencer(self) -> int:
        return (self.vencimiento - timezone.localdate()).days

    @property
    def vencido(self) -> bool:
        return self.vencimiento < timezone.localdate()

    @property
    def por_vencer(self) -> bool:
        """Vence dentro del aviso configurado y todavía no ha vencido."""
        dias = Configuracion.obtener().dias_aviso_documento
        return 0 <= self.dias_para_vencer <= dias

    @property
    def estado(self) -> str:
        if self.vencido:
            return "Vencido"
        if self.por_vencer:
            return "Por vencer"
        return "Vigente"

    @classmethod
    def proximo_vencimiento(cls, vehiculo: Vehiculo) -> date | None:
        """Fecha del documento más próximo a vencer de un vehículo."""
        return (
            cls.objects.filter(vehiculo=vehiculo)
            .order_by("vencimiento")
            .values_list("vencimiento", flat=True)
            .first()
        )


class Asignacion(models.Model):
    """Vehículo asignado a un conductor, con historial (R18).

    Solo el administrador o el superadministrador crean asignaciones; el
    conductor nunca se asigna un vehículo. Un vehículo y un conductor pueden
    tener **una sola** asignación activa a la vez: al cambiar de vehículo se
    cierra la anterior con fecha y motivo, y no se borra nada.
    """

    vehiculo = models.ForeignKey(
        Vehiculo,
        verbose_name="vehículo",
        on_delete=models.PROTECT,
        related_name="asignaciones",
    )
    conductor = models.ForeignKey(
        Conductor,
        verbose_name="conductor",
        on_delete=models.PROTECT,
        related_name="asignaciones",
    )
    fecha_inicio = models.DateField("fecha de inicio", default=timezone.localdate)
    fecha_fin = models.DateField("fecha de fin", null=True, blank=True)
    motivo_fin = models.CharField("motivo del cambio o fin", max_length=200, blank=True)

    creado_en = models.DateTimeField("creada en", auto_now_add=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="creada por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "asignación de vehículo"
        verbose_name_plural = "asignaciones de vehículo"
        ordering = ["-fecha_inicio", "-pk"]

    def __str__(self):
        return f"{self.vehiculo.placa} · {self.conductor} · desde {self.fecha_inicio:%d/%m/%Y}"

    @property
    def activa(self) -> bool:
        return self.fecha_fin is None

    def clean(self):
        super().clean()
        if self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError(
                {"fecha_fin": "La fecha de fin no puede ser anterior a la de inicio."}
            )
        if not self.activa:
            return
        # Una sola asignación activa por vehículo y por conductor.
        otras = Asignacion.objects.filter(fecha_fin__isnull=True).exclude(pk=self.pk)
        if otras.filter(vehiculo=self.vehiculo).exists():
            raise ValidationError(
                {"vehiculo": "Ese vehículo ya está asignado a otro conductor."}
            )
        if otras.filter(conductor=self.conductor).exists():
            raise ValidationError(
                {"conductor": "Ese conductor ya tiene un vehículo asignado."}
            )

    @classmethod
    def activa_de(cls, conductor: Conductor) -> "Asignacion | None":
        """Asignación vigente de un conductor, si tiene una."""
        return (
            cls.objects.filter(conductor=conductor, fecha_fin__isnull=True)
            .select_related("vehiculo")
            .first()
        )


class Servicio(models.Model):
    """Recorrido de un conductor: se inicia con km y ruta, se cierra con km.

    Reglas aplicadas:

    - **R12** el kilometraje nunca disminuye: el km inicial no puede ser menor al
      del vehículo y el final no puede ser menor al inicial.
    - El cierre **siempre** se permite; el bloqueo por documento o por licencia
      se aplica al **iniciar**.
    - Se puede cerrar **sin novedad**; la novedad como registro propio llega en
      la v0.7.
    """

    class Estado(models.TextChoices):
        EN_CURSO = "en_curso", "En curso"
        CERRADO = "cerrado", "Cerrado"

    vehiculo = models.ForeignKey(
        Vehiculo,
        verbose_name="vehículo",
        on_delete=models.PROTECT,
        related_name="servicios",
    )
    conductor = models.ForeignKey(
        Conductor,
        verbose_name="conductor",
        on_delete=models.PROTECT,
        related_name="servicios",
    )
    km_inicial = models.PositiveIntegerField("kilometraje inicial")
    ruta = models.CharField("ruta u operación", max_length=200)
    iniciado_en = models.DateTimeField("iniciado en", auto_now_add=True)

    km_final = models.PositiveIntegerField("kilometraje final", null=True, blank=True)
    cerrado_en = models.DateTimeField("cerrado en", null=True, blank=True)
    sin_novedad = models.BooleanField("cerrado sin novedad", default=True)
    observacion_cierre = models.CharField(
        "observación del cierre", max_length=200, blank=True
    )

    class Meta:
        verbose_name = "servicio"
        verbose_name_plural = "servicios"
        ordering = ["-iniciado_en", "-pk"]

    def __str__(self):
        return f"{self.vehiculo.placa} · {self.conductor} · {self.iniciado_en:%d/%m/%Y}"

    @property
    def estado(self) -> str:
        return self.Estado.EN_CURSO if self.cerrado_en is None else self.Estado.CERRADO

    @property
    def km_recorridos(self) -> int | None:
        if self.km_final is None:
            return None
        return self.km_final - self.km_inicial

    def clean(self):
        super().clean()
        if self.km_final is None:
            return
        if self.km_final < self.km_inicial:
            raise ValidationError(
                {"km_final": "El kilometraje final no puede ser menor al inicial."}
            )
        if self.cerrado_en is None:
            raise ValidationError(
                {"cerrado_en": "Si registra el kilometraje final, cierre el servicio."}
            )

    @classmethod
    def en_curso_de(cls, conductor: Conductor) -> "Servicio | None":
        return cls.objects.filter(conductor=conductor, cerrado_en__isnull=True).first()


def ruta_foto_inspeccion(instancia: "RespuestaItem", nombre_original: str) -> str:
    """Ruta de la foto de un ítem: ``fotos/inspecciones/2026/11/ABC123-frenos.png``."""
    hoy = timezone.localdate()
    extension = Path(nombre_original).suffix.lower() or ".jpg"
    nombre = instancia.item.nombre.lower().replace(" ", "-")[:40]
    placa = instancia.inspeccion.vehiculo.placa
    return f"fotos/inspecciones/{hoy:%Y/%m}/{placa}-{nombre}{extension}"


class PlantillaInspeccion(models.Model):
    """Plantilla de ítems: «rápida» (diaria) o «profunda» (semanal)."""

    class Nivel(models.TextChoices):
        RAPIDA = "rapida", "Rápida"
        PROFUNDA = "profunda", "Profunda"

    nombre = models.CharField("nombre", max_length=80)
    nivel = models.CharField(
        "nivel", max_length=10, choices=Nivel.choices, default=Nivel.RAPIDA
    )
    activa = models.BooleanField("activa", default=True)

    creado_en = models.DateTimeField("creado en", auto_now_add=True)
    actualizado_en = models.DateTimeField("actualizado en", auto_now=True)

    class Meta:
        verbose_name = "plantilla de inspección"
        verbose_name_plural = "plantillas de inspección"
        ordering = ["nivel", "nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.get_nivel_display()})"


class ItemInspeccion(models.Model):
    """Ítem de una plantilla. Los críticos detectan novedades que bloquean (R7)."""

    plantilla = models.ForeignKey(
        PlantillaInspeccion,
        verbose_name="plantilla",
        on_delete=models.CASCADE,
        related_name="items",
    )
    grupo = models.CharField("grupo", max_length=60)
    nombre = models.CharField("nombre", max_length=120)
    es_critico = models.BooleanField("crítico", default=False)
    requiere_foto = models.BooleanField("requiere foto", default=False)
    orden = models.PositiveSmallIntegerField("orden", default=0)

    class Meta:
        verbose_name = "ítem de inspección"
        verbose_name_plural = "ítems de inspección"
        ordering = ["orden", "pk"]

    def __str__(self):
        return f"{self.grupo} · {self.nombre}"


class Inspeccion(models.Model):
    """Inspección diaria, firmada con la contraseña del conductor (R6).

    El PIN nunca se guarda: ``firmar()`` solo verifica el hash existente del
    usuario y registra la hora de la firma.
    """

    class Estado(models.TextChoices):
        EN_PROGRESO = "en_progreso", "En progreso"
        FINALIZADA = "finalizada", "Finalizada"

    class Resultado(models.TextChoices):
        APROBADA = "aprobada", "Aprobada"
        BLOQUEADA = "bloqueada", "Bloqueada"

    vehiculo = models.ForeignKey(
        Vehiculo,
        verbose_name="vehículo",
        on_delete=models.PROTECT,
        related_name="inspecciones",
    )
    conductor = models.ForeignKey(
        Conductor,
        verbose_name="conductor",
        on_delete=models.PROTECT,
        related_name="inspecciones",
    )
    plantilla = models.ForeignKey(
        PlantillaInspeccion,
        verbose_name="plantilla",
        on_delete=models.PROTECT,
        related_name="inspecciones",
    )
    estado = models.CharField(
        "estado", max_length=12, choices=Estado.choices, default=Estado.EN_PROGRESO
    )
    km = models.PositiveIntegerField("kilometraje actual")
    iniciado_en = models.DateTimeField("iniciado en", auto_now_add=True)
    finalizado_en = models.DateTimeField("finalizado en", null=True, blank=True)
    duracion = models.DurationField("duración", null=True, blank=True)
    resultado = models.CharField(
        "resultado", max_length=10, choices=Resultado.choices, blank=True
    )
    firma_en = models.DateTimeField("firmada en", null=True, blank=True)
    firmada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="firmada por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    creado_en = models.DateTimeField("creado en", auto_now_add=True)

    class Meta:
        verbose_name = "inspección"
        verbose_name_plural = "inspecciones"
        ordering = ["-iniciado_en", "-pk"]

    def __str__(self):
        return f"{self.vehiculo.placa} · {self.conductor} · {self.iniciado_en:%d/%m/%Y}"

    @property
    def finalizada(self) -> bool:
        return self.estado == self.Estado.FINALIZADA

    def calcular_resultado(self) -> str:
        """R7: una novedad en un ítem crítico bloquea; si no, queda aprobada."""
        critico_con_novedad = self.respuestas.filter(
            estado=RespuestaItem.Estado.CON_NOVEDAD, item__es_critico=True
        ).exists()
        if critico_con_novedad:
            return self.Resultado.BLOQUEADA
        return self.Resultado.APROBADA

    def firmar(self, pin: str, usuario=None) -> None:
        """Cierra la inspección con la contraseña del conductor (R6).

        No se puede firmar si faltan respuestas, hay ítems «sin revisar» o el
        PIN no coincide con el hash del usuario. La contraseña nunca se guarda.
        """
        if self.finalizada:
            raise ValidationError("Esta inspección ya está finalizada.")
        if not self.respuestas.exists():
            raise ValidationError("La inspección no tiene respuestas registradas.")
        if self.respuestas.filter(estado=RespuestaItem.Estado.SIN_REVISAR).exists():
            raise ValidationError("Hay ítems sin revisar; no se puede firmar la inspección.")
        if not check_password(pin, self.conductor.usuario.password):
            raise ValidationError({"firma_pin": "La contraseña del conductor no es correcta."})

        ahora = timezone.now()
        self.estado = self.Estado.FINALIZADA
        self.resultado = self.calcular_resultado()
        self.firma_en = ahora
        self.finalizado_en = ahora
        self.duracion = ahora - self.iniciado_en
        if usuario is not None:
            self.firmada_por = usuario
        self.save(
            update_fields=[
                "estado",
                "resultado",
                "firma_en",
                "finalizado_en",
                "duracion",
                "firmada_por",
            ]
        )
        if self.resultado == self.Resultado.BLOQUEADA:
            self.crear_novedad_desde_inspeccion(usuario)

    def crear_novedad_desde_inspeccion(self, usuario=None) -> "Novedad":
        """R7: convierte la novedad crítica de la inspección en una ``Novedad``.

        Es idempotente: si la inspección ya generó su novedad, devuelve esa.
        """
        existente = Novedad.objects.filter(inspeccion=self).first()
        if existente:
            return existente

        criticas = self.respuestas.filter(
            estado=RespuestaItem.Estado.CON_NOVEDAD, item__es_critico=True
        ).select_related("item")
        resumen = "; ".join(
            f"{respuesta.item.nombre}: {respuesta.informe.strip()}"
            if respuesta.informe
            else respuesta.item.nombre
            for respuesta in criticas
        )
        return Novedad.objects.create(
            vehiculo=self.vehiculo,
            conductor=self.conductor,
            inspeccion=self,
            origen=Novedad.Origen.INSPECCION,
            severidad=Novedad.Severidad.CRITICA,
            estado=Novedad.Estado.ABIERTA,
            descripcion=f"Novedad crítica detectada en la inspección rápida: {resumen}",
            reportada_por=usuario,
        )

    @classmethod
    def aprobada_hoy(cls, vehiculo: Vehiculo) -> bool:
        """R3: ¿el vehículo tiene una inspección aprobada finalizada hoy?"""
        return cls.objects.filter(
            vehiculo=vehiculo,
            resultado=cls.Resultado.APROBADA,
            finalizado_en__date=timezone.localdate(),
        ).exists()


class RespuestaItem(models.Model):
    """Respuesta a un ítem de la inspección (R5: foto si hay novedad)."""

    class Estado(models.TextChoices):
        BUEN_ESTADO = "buen_estado", "Buen estado"
        CON_NOVEDAD = "con_novedad", "Con novedad"
        SIN_REVISAR = "sin_revisar", "Sin revisar"

    inspeccion = models.ForeignKey(
        Inspeccion,
        verbose_name="inspección",
        on_delete=models.CASCADE,
        related_name="respuestas",
    )
    item = models.ForeignKey(
        ItemInspeccion,
        verbose_name="ítem",
        on_delete=models.PROTECT,
        related_name="respuestas",
    )
    estado = models.CharField(
        "estado", max_length=12, choices=Estado.choices, default=Estado.SIN_REVISAR
    )
    informe = models.TextField("informe", blank=True)
    foto = models.ImageField(
        "foto",
        upload_to=ruta_foto_inspeccion,
        max_length=255,
        blank=True,
        validators=[validar_peso_imagen, validar_imagen_real],
    )
    registrado_en = models.DateTimeField("registrado en", auto_now_add=True)

    class Meta:
        verbose_name = "respuesta de ítem"
        verbose_name_plural = "respuestas de ítem"
        ordering = ["item__orden", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["inspeccion", "item"], name="unico_item_por_inspeccion"
            )
        ]

    def __str__(self):
        return f"{self.item.nombre} · {self.get_estado_display()}"

    def clean(self):
        super().clean()
        # R5: la foto es obligatoria cuando el ítem tiene una novedad.
        if self.estado == self.Estado.CON_NOVEDAD and not self.foto:
            raise ValidationError(
                {"foto": "La foto es obligatoria cuando el ítem tiene una novedad."}
            )


def ruta_foto_novedad(instancia: "FotoNovedad", nombre_original: str) -> str:
    """Ruta: ``fotos/novedades/2026/11/ABC123-1.png`` (se numeran las fotos)."""
    hoy = timezone.localdate()
    extension = Path(nombre_original).suffix.lower() or ".jpg"
    placa = instancia.novedad.vehiculo.placa
    numero = FotoNovedad.objects.filter(novedad=instancia.novedad).count() + 1
    return f"fotos/novedades/{hoy:%Y/%m}/{placa}-{numero}{extension}"


class Novedad(models.Model):
    """Novedad de un vehículo, con la máquina de estados del contrato §8.1."""

    class Origen(models.TextChoices):
        INSPECCION = "inspeccion", "Inspección"
        SERVICIO = "servicio", "Servicio"
        REPORTE = "reporte", "Reporte del conductor"

    class Severidad(models.TextChoices):
        BAJA = "baja", "Baja"
        MEDIA = "media", "Media"
        ALTA = "alta", "Alta"
        CRITICA = "critica", "Crítica"

    class Estado(models.TextChoices):
        ABIERTA = "ABIERTA", "Abierta"
        EN_PROCESO = "EN_PROCESO", "En proceso"
        RESUELTA = "RESUELTA", "Resuelta"
        VALIDADA = "VALIDADA", "Validada"
        RECHAZADA = "RECHAZADA", "Rechazada"

    # ABIERTA → EN_PROCESO → RESUELTA → VALIDADA; salida RECHAZADA desde las dos primeras.
    TRANSICIONES = {
        Estado.ABIERTA: (Estado.EN_PROCESO, Estado.RECHAZADA),
        Estado.EN_PROCESO: (Estado.RESUELTA, Estado.RECHAZADA),
        Estado.RESUELTA: (Estado.VALIDADA,),
        Estado.VALIDADA: (),
        Estado.RECHAZADA: (),
    }

    vehiculo = models.ForeignKey(
        Vehiculo,
        verbose_name="vehículo",
        on_delete=models.PROTECT,
        related_name="novedades",
    )
    conductor = models.ForeignKey(
        Conductor,
        verbose_name="conductor",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="novedades",
    )
    inspeccion = models.ForeignKey(
        Inspeccion,
        verbose_name="inspección de origen",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="novedades",
    )
    origen = models.CharField(
        "origen", max_length=12, choices=Origen.choices, default=Origen.REPORTE
    )
    descripcion = models.TextField("descripción")
    severidad = models.CharField(
        "severidad", max_length=10, choices=Severidad.choices, default=Severidad.MEDIA
    )
    estado = models.CharField(
        "estado", max_length=12, choices=Estado.choices, default=Estado.ABIERTA
    )
    requiere_superadmin = models.BooleanField("requiere superadmin", default=False)

    reportada_en = models.DateTimeField("reportada en", auto_now_add=True)
    actualizada_en = models.DateTimeField("actualizada en", auto_now=True)
    reportada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="reportada por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "novedad"
        verbose_name_plural = "novedades"
        ordering = ["-reportada_en", "-pk"]

    def __str__(self):
        return f"{self.vehiculo.placa} · {self.get_severidad_display()} · {self.estado}"

    def save(self, *args, **kwargs):
        if self.severidad == self.Severidad.CRITICA:
            self.requiere_superadmin = True
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.severidad == self.Severidad.CRITICA:
            self.requiere_superadmin = True

    @property
    def bloquea_vehiculo(self) -> bool:
        """R7: una crítica bloquea hasta que pasa a VALIDADA (contrato §8.1)."""
        return (
            self.severidad == self.Severidad.CRITICA
            and self.estado != self.Estado.VALIDADA
        )

    def cambiar_estado(self, estado_nuevo, usuario=None, descripcion=""):
        """Aplica una transición válida y deja constancia en ``Gestion``."""
        if estado_nuevo not in self.TRANSICIONES[self.estado]:
            raise ValidationError(
                f"No se puede pasar de {self.estado} a {estado_nuevo}."
            )
        anterior = self.estado
        self.estado = estado_nuevo
        self.save(update_fields=["estado", "actualizada_en", "requiere_superadmin"])
        Gestion.objects.create(
            novedad=self,
            usuario=usuario,
            descripcion=descripcion or f"Cambio de {anterior} a {estado_nuevo}",
        )

    @classmethod
    def criticas_de(cls, vehiculo: Vehiculo):
        """Novedades críticas que bloquean al vehículo (R7)."""
        return cls.objects.filter(
            vehiculo=vehiculo, severidad=cls.Severidad.CRITICA
        ).exclude(estado=cls.Estado.VALIDADA)


class Gestion(models.Model):
    """Actuación de un admin o superadmin sobre una novedad (contrato §7)."""

    novedad = models.ForeignKey(
        Novedad,
        verbose_name="novedad",
        on_delete=models.CASCADE,
        related_name="gestiones",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    descripcion = models.TextField("descripción")
    fecha = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        verbose_name = "gestión de novedad"
        verbose_name_plural = "gestión de novedades"
        ordering = ["-fecha", "-pk"]

    def __str__(self):
        return f"{self.novedad} · {self.fecha:%d/%m/%Y %H:%M}"


class FotoNovedad(models.Model):
    """Foto opcional de una novedad: puede haber una, varias o ninguna."""

    novedad = models.ForeignKey(
        Novedad,
        verbose_name="novedad",
        on_delete=models.CASCADE,
        related_name="fotos",
    )
    imagen = models.ImageField(
        "imagen",
        upload_to=ruta_foto_novedad,
        max_length=255,
        validators=[validar_peso_imagen, validar_imagen_real],
    )
    descripcion = models.CharField("descripción", max_length=150, blank=True)
    subida_en = models.DateTimeField("subida en", auto_now_add=True)
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="subida por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "foto de novedad"
        verbose_name_plural = "fotos de novedad"
        ordering = ["novedad", "-subida_en", "-pk"]

    def __str__(self):
        return f"{self.novedad.vehiculo.placa} · {self.nombre_archivo}"

    @property
    def nombre_archivo(self) -> str:
        return Path(self.imagen.name).name


class Autorizacion(models.Model):
    """Firma de responsabilidad para autorizar una salida con falla (R8).

    El ``hash_justificacion`` se calcula siempre en el servidor; el cliente no
    puede enviarlo. La contraseña del superadmin se verifica en la vista y
    **nunca se guarda**.
    """

    novedad = models.OneToOneField(
        Novedad,
        verbose_name="novedad",
        on_delete=models.PROTECT,
        related_name="autorizacion",
    )
    superadmin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="superadministrador",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    justificacion = models.TextField("justificación")
    hash_justificacion = models.CharField(
        "hash de la justificación", max_length=64, editable=False
    )
    ip = models.CharField("dirección IP", max_length=45, blank=True)
    fecha = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        verbose_name = "autorización de salida con falla"
        verbose_name_plural = "autorizaciones de salida con falla"
        ordering = ["-fecha", "-pk"]

    def __str__(self):
        return f"{self.novedad.vehiculo.placa} · {self.fecha:%d/%m/%Y %H:%M}"

    def save(self, *args, **kwargs):
        self.hash_justificacion = hashlib.sha256(
            self.justificacion.encode("utf-8")
        ).hexdigest()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        longitud = len(self.justificacion.strip())
        if not 20 <= longitud <= 500:
            raise ValidationError(
                {"justificacion": "La justificación debe tener entre 20 y 500 caracteres."}
            )

