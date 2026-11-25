# Guía de entorno — cómo abrir y validar el proyecto

Para alguien que nunca ha usado un entorno virtual ni PyCharm. Sigue los pasos en orden.

---

## Parte 1. Abrir el proyecto en PyCharm

1. Abre **PyCharm** (menú Inicio → busca "PyCharm").
2. En la ventana inicial elige **Open** (o `File → Open`).
3. Navega hasta:
   `P:\Proyectos\control-flota-vehicular\App`
4. Selecciona la carpeta **App** (no la carpeta `.venv`, no la carpeta padre) y pulsa **OK**.
5. Si aparece un aviso de confianza, pulsa **Trust Project**.

### 1.1 Decirle a PyCharm dónde está Python

El proyecto usa un entorno virtual (`.venv`). PyCharm debe usar **ese** Python, no el del sistema.

1. Abre `File → Settings` (atajo `Ctrl + Alt + S`).
2. En el árbol de la izquierda: `Project: App → Python Interpreter`.
3. Pulsa el engranaje ⚙ o **Add Interpreter → Add Local Interpreter**.
4. Elige **Virtualenv Environment** → pestaña **Existing**.
5. En "Interpreter" escribe o busca:
   `P:\Proyectos\control-flota-vehicular\App\.venv\Scripts\python.exe`
6. Pulsa **OK** y luego **Apply**.

**Cómo saber que quedó bien:** abajo a la derecha debe decir `Python 3.14 (.venv)`.
Si dice otra versión o "No interpreter", repite el paso 1.1.

### 1.2 Ejecutar el servidor desde PyCharm

1. En el panel izquierdo abre `manage.py`.
2. Clic derecho sobre `manage.py` → **Modify Run Configuration…**
3. En el campo **Script parameters** escribe: `runserver`
4. Verifica que **Working directory** sea la carpeta `App`.
5. Pulsa **OK** y luego el botón ▶ (Run).

**Resultado esperado en la consola:**

```
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

6. Abre el navegador en `http://127.0.0.1:8000/`.
   Debes ver el encabezado marrón "Mi Flota" y dos tarjetas.
7. Para detener: botón ⏹ (Stop) o `Ctrl + F2`.

### 1.3 Terminal dentro de PyCharm

`Alt + F12` abre la terminal. Debe aparecer `(.venv)` al inicio de la línea.
Si no aparece, escribe:

```powershell
.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea el script, ejecuta esta vez:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

Ese cambio solo dura la sesión de la terminal (no modifica el sistema).

---

## Parte 2. Validar sin PyCharm (PowerShell)

```powershell
cd "P:\Proyectos\control-flota-vehicular\App"
.venv\Scripts\python.exe manage.py runserver
```

Abrir `http://127.0.0.1:8000/` y comprobar lo mismo.

**Errores comunes:**

| Mensaje | Causa | Solución |
|---|---|---|
| `ModuleNotFoundError` | Se usó el Python del sistema | Usa `.venv\Scripts\python.exe` |
| `ImproperlyConfigured: SECRET_KEY` | Falta el archivo `.env` | Copia `.env.example` a `.env` |
| `That port is already in use` | Ya hay un servidor corriendo | Ciérralo o usa `runserver 8001` |
| Página sin estilos | No es un error | Los estilos se agregan en v0.3 |

---

## Parte 3. Conectar PostgreSQL 18 (para v0.2)

PostgreSQL **ya está instalado** en `P:\Program Files\PostgreSQL\18` y el servicio
`postgresql-x64-18` está **Running** en el puerto **5432**. Falta crear la base y el usuario
del proyecto.

### 3.1 Crear la base y el usuario

**Opción A — con pgAdmin (visual):**
1. Menú Inicio → **pgAdmin 4**.
2. Clic en `Servers → PostgreSQL 18`. Pide la contraseña del usuario `postgres`
   (la definiste al instalar PostgreSQL).
3. Clic derecho sobre `Databases` → **Create → Database…**
   - Name: `mi_flota`
   - Owner: `postgres` (se cambia después)
   - Save.
4. Clic derecho sobre `Login/Group Roles` → **Create → Login/Group Role…**
   - General → Name: `mi_flota`
   - Definition → Password: una clave fuerte
   - Privileges → Can login: **Sí**
   - Save.
5. Volver a la base `mi_flota` → Properties → Owner: `mi_flota` → Save.

**Opción B — con psql (terminal):**

```powershell
& "P:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost
```

Te pedirá la contraseña de `postgres`. Dentro de la consola SQL:

```sql
CREATE USER mi_flota WITH PASSWORD 'AquiTuClaveFuerte';
CREATE DATABASE mi_flota OWNER mi_flota;
\q
```

### 3.2 Decirle a Django que use PostgreSQL

1. Instala el conector (una sola vez):

```powershell
.venv\Scripts\python.exe -m pip install "psycopg[binary]"
```

2. Edita el archivo `.env` (está en la carpeta `App`) y deja:

```
DB_ENGINE=postgresql
DB_NAME=mi_flota
DB_USER=mi_flota
DB_PASSWORD=AquiTuClaveFuerte
DB_HOST=localhost
DB_PORT=5432
```

3. Aplica las migraciones:

```powershell
.venv\Scripts\python.exe manage.py migrate
```

4. Comprueba que quedó conectado:

```powershell
.venv\Scripts\python.exe manage.py dbshell
```

Dentro escribe `\dt` (debe listar las tablas) y `\q` para salir.

**Importante:** la contraseña va **solo** en `.env`, nunca en el código ni en Git.
Ese archivo ya está excluido por `.gitignore`.

### 3.3 Si algo falla

| Mensaje | Causa | Solución |
|---|---|---|
| `psql no se reconoce` | No está en el PATH | Usa la ruta completa del paso 3.1 |
| `password authentication failed` | Contraseña incorrecta | Verifica la clave del usuario `mi_flota` |
| `database "mi_flota" does not exist` | No se creó la base | Repite el paso 3.1 |
| `Error loading psycopg` | Falta el conector | Ejecuta el `pip install` del paso 3.2 |
| `connection refused` | Servicio detenido | `Get-Service postgresql-x64-18` y arráncalo |

---

## Parte 4. Verificación rápida del proyecto

| Comprobación | Comando | Resultado esperado |
|---|---|---|
| Configuración | `manage.py check` | `System check identified no issues` |
| Pruebas | `pytest` | Todas pasan (`238 passed` al 25/11/2026) |
| Estilo | `ruff check .` | `All checks passed!` |
| Base al día | `manage.py makemigrations --check --dry-run` | `No changes detected` |
| Página web | `manage.py runserver` | Carga en `http://127.0.0.1:8000/` |

---

## Parte 5. Configurar el correo saliente (Gmail)

Objetivo: que la aplicación pueda enviar avisos desde `miflota.granjero@gmail.com`.
Se hace una sola vez por equipo.

> **Django 6:** la configuración vive en `MAILERS`, dentro de `config/settings.py`.
> Las variables del `.env` se siguen llamando `EMAIL_*` porque así se documentan en
> Gmail y en la mayoría de proveedores. Si `EMAIL_HOST` está vacío, los correos se
> imprimen en la consola y no se envía nada: el proyecto funciona igual.

### 5.1 Crear la contraseña de aplicación

Requisito: la verificación en dos pasos debe estar activa en la cuenta.

1. Entra a `myaccount.google.com/apppasswords` (o Seguridad → Verificación en dos pasos → Contraseñas de aplicaciones).
2. Nombre: `Mi Flota - correo`. Pulsa **Crear**.
3. Copia los **16 caracteres sin espacios**. Google los muestra una sola vez.
4. Guarda esa contraseña en un lugar privado. **No es** la contraseña de la cuenta.

### 5.2 Escribirla en el `.env`

El archivo `.env` está en la carpeta `App` y no se sube a Git. Contiene un bloque
con un marcador; reemplaza **solo** la línea marcada:

| Variable | Valor en este proyecto |
|---|---|
| `EMAIL_HOST` | `smtp.gmail.com` |
| `EMAIL_PORT` | `587` |
| `EMAIL_HOST_USER` | `miflota.granjero@gmail.com` |
| `EMAIL_HOST_PASSWORD` | la contraseña de aplicación de 16 caracteres |
| `EMAIL_USE_TLS` | `True` |
| `EMAIL_TIMEOUT` | `20` |
| `DEFAULT_FROM_EMAIL` | `Mi Flota <miflota.granjero@gmail.com>` |

### 5.3 Probar el envío

Desde la carpeta `App`:

```powershell
.venv\Scripts\python.exe manage.py comprobar_correo
```

Envía la prueba a la misma cuenta. Si llega, el canal funciona. Para enviarla a
otra dirección:

```powershell
.venv\Scripts\python.exe manage.py comprobar_correo --para otro@correo.com
```

### 5.4 Si algo falla

| Mensaje | Causa | Solución |
|---|---|---|
| Gmail rechazó el usuario o la contraseña | Se usó la contraseña de la cuenta o el correo está incompleto | Repite el paso 5.1 y copia los 16 caracteres sin espacios |
| No se pudo conectar con smtp.gmail.com:587 | Red, firewall o antivirus | Prueba otra red y revisa que el puerto 587 no esté bloqueado |
| «el correo se imprime en esta consola» | Falta `EMAIL_HOST` en el `.env` | Revisa que el bloque se guardó y que no quedó comentado |
| Llega a spam | Remitente nuevo sin historial | Marca «no es spam» una vez; al ser la misma cuenta suele corregirse |

### 5.5 Límites de una cuenta Gmail normal

Unos 500 destinatarios al día y sin garantía de servicio. Para los avisos de la
flota es suficiente; para campañas masivas habría que pasar a un proveedor
transaccional (Brevo, Resend) con el dominio propio.

---

## Parte 6. Configurar Telegram

El bot **@MiFlotaGranjeroBot** ya existe y su token está guardado solo en `App\.env`,
en la variable `TELEGRAM_BOT_TOKEN`. Si algún día hay que crearlo de nuevo:

1. Abre `https://t.me/BotFather` y envía `/newbot`.
2. Nombre visible: `Mi Flota Avisos`. Usuario: `MiFlotaGranjeroBot` (debe terminar en `bot`).
3. Copia el token que entrega BotFather y pégalo **solo** en `App\.env`, sin comillas ni espacios.
4. Abre `https://t.me/MiFlotaGranjeroBot`, pulsa **Iniciar** y envía `hola`.
   Un bot no puede escribirle primero a nadie: sin este paso no hay chat_id.
5. Guarda el chat_id en el usuario, en `/maestros/usuarios/` → campo **chat de Telegram**.
   En un chat privado ese número es el ID numérico de la persona.

### 6.1 Probarlo

```powershell
.venv\Scripts\python.exe manage.py comprobar_telegram --sin-envio
.venv\Scripts\python.exe manage.py comprobar_telegram
```

El primero verifica el token con `getMe`; el segundo además envía un mensaje de
prueba al último chat que haya escrito al bot. El comando **nunca imprime el token**.
Si se filtra, en BotFather envía `/revoke` y actualiza el `.env`.

| Mensaje | Causa | Solución |
|---|---|---|
| `Falta TELEGRAM_BOT_TOKEN` | Marcador sin reemplazar | Pega el token en `.env` |
| `Telegram rechazó el token: 401` | Token revocado o mal copiado | `/revoke` y pegar el nuevo |
| `No hay ningún chat iniciado` | Nadie pulsó Iniciar | Paso 4 de esta sección |
| `429 ... Vuelve a intentarlo en N s` | Demasiados mensajes | La cola respeta `retry_after` y reintenta |

Límites: unos 30 mensajes/segundo en total y 1 por segundo por chat. Para enviar
avisos **no hace falta webhook**; solo haría falta si el bot recibiera comandos.

---

## Parte 7. Web Push (VAPID)

Las claves ya están generadas en `App\.env` y **no se regeneran**: si cambian, los
navegadores deben volver a suscribirse. No se muestran completas en ninguna
pantalla; en `/notificaciones/canales/` solo aparece una huella SHA-256.

Para activar los avisos en un navegador:

1. Inicia sesión y entra a `/notificaciones/preferencias/`.
2. Marca «Recibir urgencias en el navegador (Web Push)» y guarda.
3. Pulsa **Activar avisos en este navegador** y concede el permiso.
   El navegador envía su suscripción a `/notificaciones/suscribir/` y se guarda
   en la tabla `SuscripcionPush`.

El service worker está en `/sw.js` y el manifiesto PWA en `/static/manifest.webmanifest`.
Con la pestaña cerrada, el aviso llega mientras el navegador siga abierto.

**HTTPS es obligatorio** fuera del equipo local (`localhost` sí funciona sin HTTPS).
En iPhone, además, hay que instalar la PWA (iOS 16.4 o superior); mientras tanto,
el correo y Telegram cubren ese canal.

---

## Parte 8. Cola de notificaciones y resumen diario

Los eventos del contrato (novedad crítica, solicitud de autorización, autorización
concedida, vencimientos, inspecciones pendientes y mantenimientos) crean filas en
`Notificacion`. Nada se envía en el momento: un programador ejecuta la cola.

```powershell
.venv\Scripts\python.exe manage.py enviar_notificaciones
.venv\Scripts\python.exe manage.py enviar_notificaciones --resumen
.venv\Scripts\python.exe manage.py enviar_notificaciones --mediodia
```

Reglas: 3 intentos por canal con espera 60 s, 120 s y 240 s; el error queda en la
fila. Los críticos no se pueden silenciar (R15) y se repiten por los 4 canales a
los 5 minutos si nadie los abre. `--resumen` genera el aviso de las 7:00 a. m. y
`--mediodia` avisa de las inspecciones que siguen en progreso. El cierre de
servicio con novedad avisa automáticamente al administrador desde la pantalla
del conductor.

En este PC ya están registradas tres tareas del Programador de tareas de Windows:

| Tarea | Frecuencia | Comando |
|---|---|---|
| `MiFlota-Cola-Notificaciones` | Cada minuto | `enviar_notificaciones` |
| `MiFlota-Resumen-Diario` | Diaria 07:00 | `enviar_notificaciones --resumen` |
| `MiFlota-Inspecciones-Mediodia` | Diaria 12:00 | `enviar_notificaciones --mediodia` |

Se crearon con `scripts\registrar_tareas_notificaciones.ps1` (sin contraseñas: usan la
sesión del usuario actual, así que deben estar iniciadas en Windows). Para volver a
registrarlas tras cambiar de equipo:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\registrar_tareas_notificaciones.ps1
```

Para revisarlas: `Get-ScheduledTask -TaskName 'MiFlota-*' | Select TaskName,State`.
En producción, un `cron` equivalente. Los parámetros se ajustan en el `.env` con
`NOTIFICACIONES_INTENTOS`, `NOTIFICACIONES_ESPERA` y
`NOTIFICACIONES_ESCALAMIENTO_MINUTOS`.
