"""Modelos de la flota: vehículo, conductor, documento y configuración.

Reglas del proyecto que se aplican aquí (``docs/DOCUMENTO_MAESTRO.md``, sección 7):

- **R11** un documento vencido del **vehículo** lo bloquea.
- **R12** el kilometraje nunca puede disminuir.
- **R19** todo documento debería tener soporte digital (foto o PDF); puede
  registrarse sin él y queda «pendiente» hasta que se suba.
- **R20** la baja de un conductor no borra nada: marca fechas y motivo.
- **R21** la licencia vencida inhabilita al **conductor**, no al vehículo.

Los estados ``EN_SERVICIO``, ``BLOQUEADO_NOVEDAD`` y ``EN_MANTENIMIENTO`` se
activarán en las versiones que crean servicios, novedades y mantenimientos; por
ahora solo se calculan los que dependen de los documentos y de la baja.
"""

from datetime import date
from pathlib import Path

from django.conf import settings
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
        """Estado calculado (R11). Los demás estados llegan con sus versiones."""
        if not self.activo:
            return self.Estado.FUERA_DE_SERVICIO
        if self.documentos_vencidos.exists():
            return self.Estado.BLOQUEADO_DOCUMENTO
        return self.Estado.OPERATIVO


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
