# Mi Flota

Sistema de control de flota para el transporte de huevos: inspecciones
preoperacionales, novedades, documentos, mantenimiento y hoja de vida por placa.

Proyecto en construcción por versiones. Estado actual: **v0.1 (entorno)**.

## Requisitos

- Python 3.14
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

# 5. Crear la base de datos
python manage.py migrate

# 6. Arrancar
python manage.py runserver
```

Abre http://127.0.0.1:8000/ y verás la página de verificación.

## Comandos útiles

| Comando | Para qué sirve |
|---|---|
| `python manage.py runserver` | Arranca el servidor de desarrollo |
| `python manage.py makemigrations` | Genera migraciones tras cambiar modelos |
| `python manage.py migrate` | Aplica los cambios a la base de datos |
| `python manage.py createsuperuser` | Crea un administrador del panel |
| `pytest` | Ejecuta las pruebas |
| `ruff check .` | Revisa el estilo del código |

## Estructura

```
App\
├── config\            Configuración del proyecto (settings, urls, vistas base)
├── apps\
│   └── usuarios\      Usuario personalizado con roles
├── templates\         Plantillas HTML
├── static\            CSS, imágenes y JavaScript
├── tests\             Pruebas automatizadas
├── requirements.txt   Dependencias con versión fija
└── .env               Secretos locales (no se versiona)
```

## Reglas del proyecto

- Ningún secreto se escribe en el código: todo va en `.env`.
- Los roles son `conductor`, `admin` y `superadmin`.
- La lógica de negocio se valida en el servidor, nunca solo en el navegador.
- Cada versión se entrega con pruebas que pasan.
