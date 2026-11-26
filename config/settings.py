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

# Producción detrás de Cloudflare Tunnel: el túnel envía X-Forwarded-Proto: https.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Dominios HTTPS permitidos por CSRF (se completan en el .env al elegir el dominio).
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=False, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=False, cast=bool)
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)

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
    "apps.notificaciones",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # En producción sirve CSS, JS, sw.js y el manifiesto sin necesidad de nginx.
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
                "apps.notificaciones.context_processors.badge",
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

# ---------------------------------------------------------------------------
# Notificaciones (v1.0)
# ---------------------------------------------------------------------------
# Telegram: el token se lee del .env y nunca se muestra en pantalla ni en Git.
TELEGRAM_BOT_TOKEN = config("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_API_URL = config("TELEGRAM_API_URL", default="https://api.telegram.org")
TELEGRAM_TIMEOUT = config("TELEGRAM_TIMEOUT", default=10, cast=int)

# Web Push: par de claves VAPID. La privada está en base64 dentro del .env.
VAPID_PUBLIC_KEY = config("VAPID_PUBLIC_KEY", default="")
VAPID_PRIVATE_KEY_B64 = config("VAPID_PRIVATE_KEY_B64", default="")
VAPID_ADMIN_EMAIL = config("VAPID_ADMIN_EMAIL", default="")
WEB_PUSH_TIMEOUT = config("WEB_PUSH_TIMEOUT", default=10, cast=int)

# Cola de envíos: 3 intentos, espera creciente y escalamiento a los 5 minutos.
NOTIFICACIONES_INTENTOS = config("NOTIFICACIONES_INTENTOS", default=3, cast=int)
NOTIFICACIONES_ESPERA = config("NOTIFICACIONES_ESPERA", default=60, cast=int)
NOTIFICACIONES_ESCALAMIENTO_MINUTOS = config(
    "NOTIFICACIONES_ESCALAMIENTO_MINUTOS", default=5, cast=int
)
