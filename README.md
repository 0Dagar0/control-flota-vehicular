# Mi Flota

Sistema de control de flota para el transporte de huevos: inspecciones
preoperacionales, novedades, documentos, mantenimiento y hoja de vida por placa.

Proyecto en construcción por versiones. Estado actual: **v1.1 (mantenimientos e
incidentes)** publicada en `origin/master`, más la **galería de fotos**, el **correo
SMTP**, el **bot de Telegram** y las **claves VAPID** listos para la v1.0, con
**238 pruebas en verde**. El backend de la **v1.0 (notificaciones)** está
**publicado en `origin/master` = `915434e`** y el encargo 05 de diseño quedó ejecutado;
falta el despliegue con HTTPS para que Web Push funcione fuera del PC y la revisión
visual de las maquetas.

## Requisitos

- Python 3.14
- PostgreSQL 18 (el proyecto no usa SQLite en desarrollo)
- Git

## Puesta en marcha

```powershell
# 1. Crear el entorno virtual (solo la primera vez)
py -3.14 -m venv .venv

# 2. Activar el entorno
.venv\Scripts\Activate.ps1

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Crear el archivo de configuración local
Copy-Item .env.example .env
# Luego edita .env y pon una SECRET_KEY propia:
#   python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"

# 5. Crear la base y el rol en PostgreSQL (solo la primera vez)
powershell -File scripts\crear_base_postgres.ps1

# 6. Aplicar migraciones y cargar la plantilla de inspección
python manage.py migrate
python manage.py cargar_plantilla_inspeccion

# 7. Arrancar
python manage.py runserver
```

Abre http://127.0.0.1:8000/ e inicia sesión con la cédula del usuario.

## Comandos útiles

| Comando | Para qué sirve |
|---|---|
| `python manage.py runserver` | Arranca el servidor de desarrollo |
| `python manage.py makemigrations` | Genera migraciones tras cambiar modelos |
| `python manage.py migrate` | Aplica los cambios a la base de datos |
| `python manage.py cargar_plantilla_inspeccion` | Crea o actualiza la plantilla «Rápida» (7 ítems) |
| `python manage.py cargar_flota_inicial` | Carga los datos de flota (idempotente) |
| `python manage.py comprobar_correo` | Envía un correo de prueba con el SMTP del `.env` |
| `python manage.py comprobar_telegram` | Verifica el bot y envía un mensaje de prueba (sin mostrar el token) |
| `python manage.py enviar_notificaciones` | Procesa la cola: envíos, 3 reintentos y escalamiento |
| `python manage.py enviar_notificaciones --resumen` | Genera y envía el resumen de las 7:00 a. m. |
| `python manage.py createsuperuser` | Crea un administrador del panel de Django |
| `pytest` | Ejecuta las pruebas |
| `ruff check .` | Revisa el estilo del código |

Las tareas `MiFlota-*` del Programador de tareas de Windows ejecutan la cola cada minuto, el
resumen a las 07:00 y las inspecciones al mediodía. Se registran con
`powershell -ExecutionPolicy Bypass -File scripts\registrar_tareas_notificaciones.ps1`.

## Estructura

```
App\
├── config\              Configuración del proyecto (settings, urls, vistas base)
├── apps\
│   ├── usuarios\        Usuario personalizado con roles
│   ├── flota\           Vehículos, documentos, inspecciones, novedades, mantenimientos
│   ├── maestros\        Formularios y vistas de /maestros/ (sin modelos)
│   ├── servicio\        Servicio del conductor (iniciar y cerrar)
│   └── notificaciones\  v1.0: bandeja, canales, preferencias y cola de envío
├── templates\           Plantillas HTML
├── static\              CSS, service worker, manifiesto PWA y JavaScript
├── docs\                Documento maestro, contrato front/back y guía de entorno
├── datos\               Carga inicial (los datos reales no se versionan)
├── scripts\             Utilidades (creación de la base PostgreSQL)
├── requirements.txt     Dependencias con versión fija
└── .env                 Secretos locales (no se versiona)
```

Las pruebas viven en `apps/<app>/tests/`.

## Versiones

- v0.1 Entorno · v0.2 Modelos de flota · v0.3 Acceso · v0.4 Maestros · v0.5 Servicio
- v0.6 Inspección rápida · v0.7 Novedades · v0.8 Autorización · v0.9 Documentos
- v0.10 Panel y hoja de vida 360° · v1.1 Mantenimientos e incidentes
- **v1.0 Notificaciones:** backend implementado; queda desplegar con HTTPS y entregar las maquetas del encargo 05

El detalle completo está en `docs/DOCUMENTO_MAESTRO.md`.

## Reglas del proyecto

- Ningún secreto se escribe en el código: todo va en `.env`.
- Los roles son `conductor`, `admin` y `superadmin`.
- La lógica de negocio se valida en el servidor, nunca solo en el navegador.
- Cada versión se entrega con pruebas que pasan.
- `MEMORY.md` y los datos reales del cliente no se publican: están en `.gitignore`.
