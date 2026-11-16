"""Formularios de los datos maestros: vehículos, conductores y usuarios.

Solo los usa el superadministrador (contrato §5.3). Las validaciones de negocio
viven en los modelos (R12, R19, R20, R21); aquí solo se completan los datos que
el modelo no puede saber por sí solo, como la contraseña o el usuario asociado.
"""

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.flota.models import Asignacion, Conductor, Vehiculo
from apps.usuarios.models import Usuario


class VehiculoForm(forms.ModelForm):
    """Alta y edición de un vehículo.

    El kilometraje no puede bajar (R12): lo valida ``Vehiculo.clean`` y el
    formulario lo hereda al llamar a ``full_clean``.
    """

    class Meta:
        model = Vehiculo
        fields = [
            "placa",
            "marca",
            "referencia",
            "modelo",
            "tipo_carroceria",
            "vin",
            "motor",
            "combustible",
            "km_actual",
            "propietario",
        ]
        help_texts = {
            "placa": "3 letras y 3 dígitos, por ejemplo ABC123.",
            "vin": "17 caracteres. Puede quedar vacío si no lo tiene a mano.",
        }

    def clean_placa(self):
        """Acepta la placa en minúsculas y la guarda siempre en mayúsculas."""
        return self.cleaned_data["placa"].strip().upper()


class ConductorCompletoForm(forms.Form):
    """Alta y edición de un conductor junto con su usuario de acceso.

    Un conductor necesita dos registros: el usuario (con cédula, correo y
    contraseña) y la ficha del conductor (licencia y contactos). Se piden en la
    misma pantalla para no obligar a crear el usuario primero en el admin.
    """

    documento = forms.CharField(label="cédula", max_length=20)
    first_name = forms.CharField(label="nombres", max_length=150)
    last_name = forms.CharField(label="apellidos", max_length=150)
    email = forms.EmailField(label="correo electrónico")
    telefono = forms.CharField(label="teléfono", max_length=20, required=False)
    password1 = forms.CharField(
        label="contraseña", widget=forms.PasswordInput, required=False,
        help_text="Mínimo 10 caracteres. Al editar, déjala vacía para no cambiarla.",
    )
    password2 = forms.CharField(
        label="repetir contraseña", widget=forms.PasswordInput, required=False
    )
    licencia_categoria = forms.ChoiceField(
        label="categoría de la licencia", choices=Conductor.CategoriaLicencia.choices
    )
    licencia_vencimiento = forms.DateField(
        label="vencimiento de la licencia",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    contacto_emergencia_nombre = forms.CharField(
        label="contacto de emergencia", max_length=80, required=False
    )
    contacto_emergencia_telefono = forms.CharField(
        label="teléfono de emergencia", max_length=20, required=False
    )

    def __init__(self, *args, conductor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.conductor = conductor
        if conductor is None:
            self.fields["password1"].required = True
            self.fields["password2"].required = True
            return
        usuario = conductor.usuario
        self.fields["documento"].initial = usuario.documento
        self.fields["first_name"].initial = usuario.first_name
        self.fields["last_name"].initial = usuario.last_name
        self.fields["email"].initial = usuario.email
        self.fields["telefono"].initial = usuario.telefono
        self.fields["licencia_categoria"].initial = conductor.licencia_categoria
        self.fields["licencia_vencimiento"].initial = conductor.licencia_vencimiento
        self.fields["contacto_emergencia_nombre"].initial = (
            conductor.contacto_emergencia_nombre
        )
        self.fields["contacto_emergencia_telefono"].initial = (
            conductor.contacto_emergencia_telefono
        )

    def clean_documento(self):
        documento = self.cleaned_data["documento"].strip()
        existentes = Usuario.objects.filter(documento=documento)
        if self.conductor:
            existentes = existentes.exclude(pk=self.conductor.usuario_id)
        if existentes.exists():
            raise ValidationError("Ya hay un usuario con esa cédula.")
        return documento

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        existentes = Usuario.objects.filter(email__iexact=email)
        if self.conductor:
            existentes = existentes.exclude(pk=self.conductor.usuario_id)
        if existentes.exists():
            raise ValidationError("Ya hay un usuario con ese correo.")
        return email

    def clean(self):
        datos = super().clean()
        clave1 = datos.get("password1")
        clave2 = datos.get("password2")
        if clave1 != clave2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        if clave1:
            # Las reglas de seguridad de Django (largo, no numérica, no común).
            try:
                validate_password(clave1)
            except ValidationError as error:
                self.add_error("password1", error)
        return datos

    @transaction.atomic
    def save(self) -> Conductor:
        datos = self.cleaned_data
        if self.conductor is None:
            usuario = Usuario.objects.create_user(
                documento=datos["documento"],
                email=datos["email"],
                password=datos["password1"],
                first_name=datos["first_name"],
                last_name=datos["last_name"],
                telefono=datos["telefono"],
                rol=Usuario.Rol.CONDUCTOR,
            )
            conductor = Conductor(usuario=usuario)
        else:
            conductor = self.conductor
            usuario = conductor.usuario
            usuario.documento = datos["documento"]
            usuario.email = datos["email"]
            usuario.first_name = datos["first_name"]
            usuario.last_name = datos["last_name"]
            usuario.telefono = datos["telefono"]
            usuario.save()
            if datos.get("password1"):
                usuario.set_password(datos["password1"])
                usuario.save(update_fields=["password"])

        conductor.licencia_categoria = datos["licencia_categoria"]
        conductor.licencia_vencimiento = datos["licencia_vencimiento"]
        conductor.contacto_emergencia_nombre = datos["contacto_emergencia_nombre"]
        conductor.contacto_emergencia_telefono = datos["contacto_emergencia_telefono"]
        # Valida R20/R21 y guarda.
        conductor.full_clean()
        conductor.save()
        return conductor


class UsuarioForm(forms.Form):
    """Alta y edición de administradores (contrato §5.3)."""

    ROLES = [(Usuario.Rol.ADMIN, "Administrador"), (Usuario.Rol.SUPERADMIN, "Superadministrador")]

    documento = forms.CharField(label="cédula", max_length=20)
    first_name = forms.CharField(label="nombres", max_length=150)
    last_name = forms.CharField(label="apellidos", max_length=150)
    email = forms.EmailField(label="correo electrónico")
    telefono = forms.CharField(label="teléfono", max_length=20, required=False)
    rol = forms.ChoiceField(label="rol", choices=ROLES)
    telegram_chat_id = forms.CharField(
        label="chat de Telegram", max_length=50, required=False,
        help_text="Opcional: se usa para enviar notificaciones por Telegram.",
    )
    password1 = forms.CharField(
        label="contraseña", widget=forms.PasswordInput, required=False,
        help_text="Mínimo 10 caracteres. Al editar, déjala vacía para no cambiarla.",
    )
    password2 = forms.CharField(
        label="repetir contraseña", widget=forms.PasswordInput, required=False
    )

    def __init__(self, *args, usuario=None, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        self.actor = actor
        if usuario is None:
            self.fields["password1"].required = True
            self.fields["password2"].required = True
            return
        self.fields["documento"].initial = usuario.documento
        self.fields["first_name"].initial = usuario.first_name
        self.fields["last_name"].initial = usuario.last_name
        self.fields["email"].initial = usuario.email
        self.fields["telefono"].initial = usuario.telefono
        self.fields["rol"].initial = usuario.rol
        self.fields["telegram_chat_id"].initial = usuario.telegram_chat_id

    def clean_documento(self):
        documento = self.cleaned_data["documento"].strip()
        existentes = Usuario.objects.filter(documento=documento)
        if self.usuario:
            existentes = existentes.exclude(pk=self.usuario.pk)
        if existentes.exists():
            raise ValidationError("Ya hay un usuario con esa cédula.")
        return documento

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        existentes = Usuario.objects.filter(email__iexact=email)
        if self.usuario:
            existentes = existentes.exclude(pk=self.usuario.pk)
        if existentes.exists():
            raise ValidationError("Ya hay un usuario con ese correo.")
        return email

    def clean_rol(self):
        rol = self.cleaned_data["rol"]
        # Evita que el superadmin se quite a sí mismo el permiso y se quede fuera.
        if self.usuario and self.actor and self.usuario.pk == self.actor.pk:
            if rol != Usuario.Rol.SUPERADMIN:
                raise ValidationError("No puedes quitarte tu propio rol de superadministrador.")
        return rol

    def clean(self):
        datos = super().clean()
        clave1 = datos.get("password1")
        clave2 = datos.get("password2")
        if clave1 != clave2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        if clave1:
            try:
                validate_password(clave1)
            except ValidationError as error:
                self.add_error("password1", error)
        return datos

    @transaction.atomic
    def save(self) -> Usuario:
        datos = self.cleaned_data
        if self.usuario is None:
            return Usuario.objects.create_user(
                documento=datos["documento"],
                email=datos["email"],
                password=datos["password1"],
                first_name=datos["first_name"],
                last_name=datos["last_name"],
                telefono=datos["telefono"],
                rol=datos["rol"],
                telegram_chat_id=datos["telegram_chat_id"],
            )
        usuario = self.usuario
        usuario.documento = datos["documento"]
        usuario.email = datos["email"]
        usuario.first_name = datos["first_name"]
        usuario.last_name = datos["last_name"]
        usuario.telefono = datos["telefono"]
        usuario.rol = datos["rol"]
        usuario.telegram_chat_id = datos["telegram_chat_id"]
        usuario.save()
        if datos.get("password1"):
            usuario.set_password(datos["password1"])
            usuario.save(update_fields=["password"])
        return usuario


class AsignarVehiculoForm(forms.Form):
    """Asignación de vehículo a un conductor (solo admin o superadmin).

    Un conductor tiene un vehículo a la vez. Al cambiarlo se cierra la
    asignación anterior con fecha y motivo: el historial no se borra (R18).
    """

    vehiculo = forms.ModelChoiceField(
        label="vehículo", queryset=Vehiculo.objects.none(), empty_label="Selecciona un vehículo"
    )
    fecha_inicio = forms.DateField(
        label="desde qué fecha",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        initial=timezone.localdate,
    )
    motivo = forms.CharField(
        label="motivo del cambio",
        max_length=200,
        required=False,
        help_text="Opcional. Queda guardado cuando se reemplaza una asignación anterior.",
    )

    def __init__(self, *args, conductor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.conductor = conductor
        ocupados = Asignacion.objects.filter(fecha_fin__isnull=True).exclude(
            conductor=conductor
        )
        self.fields["vehiculo"].queryset = (
            Vehiculo.objects.filter(activo=True)
            .exclude(pk__in=ocupados.values_list("vehiculo_id", flat=True))
            .order_by("placa")
        )
        actual = Asignacion.activa_de(conductor) if conductor else None
        if actual:
            self.fields["vehiculo"].initial = actual.vehiculo
            self.fields["fecha_inicio"].initial = actual.fecha_inicio

    def clean(self):
        datos = super().clean()
        actual = Asignacion.activa_de(self.conductor) if self.conductor else None
        fecha = datos.get("fecha_inicio")
        if actual and fecha and fecha < actual.fecha_inicio:
            self.add_error(
                "fecha_inicio",
                f"La asignación actual empezó el {actual.fecha_inicio:%d/%m/%Y}; "
                "la nueva no puede empezar antes.",
            )
        return datos

    @transaction.atomic
    def save(self, usuario=None) -> Asignacion:
        conductor = self.conductor
        elegido = self.cleaned_data["vehiculo"]
        fecha = self.cleaned_data["fecha_inicio"]
        motivo = self.cleaned_data["motivo"].strip() or "Cambio de vehículo"

        actual = Asignacion.activa_de(conductor)
        if actual and actual.vehiculo_id == elegido.pk:
            return actual
        if actual:
            actual.fecha_fin = fecha
            actual.motivo_fin = motivo
            actual.full_clean()
            actual.save()

        nueva = Asignacion(
            vehiculo=elegido,
            conductor=conductor,
            fecha_inicio=fecha,
            creado_por=usuario,
        )
        nueva.full_clean()
        nueva.save()
        return nueva


class BajaConductorForm(forms.Form):
    """Baja de un conductor sin borrar su historial (R20)."""

    fecha_baja = forms.DateField(
        label="fecha de la baja",
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=timezone.localdate,
    )
    motivo_baja = forms.CharField(
        label="motivo de la baja",
        max_length=200,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Queda guardado en el historial. Nada se borra.",
    )

    def clean_fecha_baja(self):
        fecha = self.cleaned_data["fecha_baja"]
        if fecha > timezone.localdate():
            raise ValidationError("La fecha de baja no puede ser futura.")
        return fecha
