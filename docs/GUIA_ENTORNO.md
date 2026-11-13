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
| Pruebas | `pytest` | `2 passed` |
| Estilo | `ruff check .` | `All checks passed!` |
| Base al día | `manage.py makemigrations --check --dry-run` | `No changes detected` |
| Página web | `manage.py runserver` | Carga en `http://127.0.0.1:8000/` |
