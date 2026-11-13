from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class UsuarioManager(UserManager):
    """Manager que crea usuarios usando el documento como credencial.

    Django trae un manager que exige `username`. Como aquí el documento
    reemplaza al usuario, hay que adaptarlo.
    """

    def _crear(self, documento, email, password, **extra_fields):
        if not documento:
            raise ValueError("El documento es obligatorio")
        email = self.normalize_email(email)
        usuario = self.model(documento=documento, email=email, **extra_fields)
        usuario.password = make_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, documento, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._crear(documento, email, password, **extra_fields)

    def create_superuser(self, documento, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("rol", self.model.Rol.SUPERADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("El superusuario debe tener is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("El superusuario debe tener is_superuser=True")

        return self._crear(documento, email, password, **extra_fields)


class Usuario(AbstractUser):
    """Usuario único del sistema, con rol y documento como credencial.

    Se usa un usuario personalizado desde la primera migración porque
    Django recomienda definirlo al inicio del proyecto: cambiarlo después
    obliga a reconstruir la base de datos.
    """

    class Rol(models.TextChoices):
        CONDUCTOR = "conductor", "Conductor"
        ADMIN = "admin", "Administrador"
        SUPERADMIN = "superadmin", "Superadministrador"

    # El campo `username` de Django se reemplaza por el documento.
    username = None

    documento = models.CharField("documento", max_length=20, unique=True)
    email = models.EmailField("correo electrónico", unique=True)
    telefono = models.CharField("teléfono", max_length=20, blank=True)
    rol = models.CharField("rol", max_length=20, choices=Rol.choices, default=Rol.CONDUCTOR)
    telegram_chat_id = models.CharField("chat de Telegram", max_length=50, blank=True)

    USERNAME_FIELD = "documento"
    REQUIRED_FIELDS = ["email", "first_name", "last_name"]

    objects = UsuarioManager()

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return f"{self.get_full_name() or self.documento} ({self.documento})"

    @property
    def es_superadmin(self):
        return self.rol == self.Rol.SUPERADMIN

    @property
    def es_admin(self):
        return self.rol in (self.Rol.ADMIN, self.Rol.SUPERADMIN)

    @property
    def es_conductor(self):
        return self.rol == self.Rol.CONDUCTOR
