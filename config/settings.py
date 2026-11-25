"""Configuración del proyecto "Mi Flota".

Las variables sensibles (clave secreta, base de datos, correo) se leen
del archivo `.env`, que NO se versiona en Git.

Para empezar: copia `.env.example` a `.env` y ajusta los valores.
"""

from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Seguridad
# ---------------------------------------------------------------------------
SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

# ---------------------------------------------------------------------------
# Aplicaciones
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.usuarios",
    "apps.flota",
    "apps.maestros",
    "apps.servicio",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------
# En desarrollo usamos SQLite (no requiere instalar nada).
# En v0.2 pasamos a PostgreSQL cambiando DB_ENGINE y las credenciales del .env.
DB_ENGINE = config("DB_ENGINE", default="sqlite3")

if DB_ENGINE == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME"),
            "USER": config("DB_USER"),
            "PASSWORD": config("DB_PASSWORD"),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------------------------------------------------------------------
# Usuario y autenticación
# ---------------------------------------------------------------------------
# Se define antes de la primera migración: cambiarlo después es muy costoso.
AUTH_USER_MODEL = "usuarios.Usuario"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
# Tras entrar, cada rol va a su pantalla desde la portada (/).
LOGIN_REDIRECT_URL = "inicio"
LOGOUT_REDIRECT_URL = "login"

# ---------------------------------------------------------------------------
# Idioma y zona horaria
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Archivos estáticos y multimedia
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Correo
# ---------------------------------------------------------------------------
# Con EMAIL_HOST en el .env se envía de verdad por SMTP; sin él los correos se
# imprimen en la consola, para que el proyecto funcione en un equipo sin
# credenciales. En Django 6 la configuración va en MAILERS y ya no se permite
# definir EMAIL_HOST, EMAIL_PORT, etc.: por eso se leen en variables privadas.
_correo_host = config("EMAIL_HOST", default="")
_correo_puerto = config("EMAIL_PORT", default=587, cast=int)
_correo_usuario = config("EMAIL_HOST_USER", default="")
_correo_clave = config("EMAIL_HOST_PASSWORD", default="")
_correo_tls = config("EMAIL_USE_TLS", default=True, cast=bool)
_correo_espera = config("EMAIL_TIMEOUT", default=20, cast=int)

DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL", default="Mi Flota <no-responder@localhost>"
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# Remitente de la cuenta SMTP (también el destinatario por defecto de la prueba).
CORREO_REMITENTE = _correo_usuario

if _correo_host:
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {
                "host": _correo_host,
                "port": _correo_puerto,
                "username": _correo_usuario,
                "password": _correo_clave,
                "use_tls": _correo_tls,
                "timeout": _correo_espera,
            },
        },
    }
else:
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.console.EmailBackend",
        },
    }
