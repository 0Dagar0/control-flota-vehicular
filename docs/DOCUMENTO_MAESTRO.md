# Documento maestro — Mi Flota

**Sistema de control de flota para transporte de huevos**
Versión del documento: 1.0 · Fecha: 2026-11-09
Ubicación del proyecto: `P:\Proyectos\control-flota-vehicular\App`

Este documento reemplaza y unifica: `PRESENTACIÓN DEL PROYECTO.docx`, `Contrato Front Back.rtf`,
`Interfaz.docx`, `notas para el programa.docx`, `Pasos.docx` y `Pasos para verificar vehiculos.docx`.
Cuando algo contradiga este documento, manda este.

---

## 1. Resumen ejecutivo

La empresa transporta huevos con una flota que hoy son **7 vehículos**, operada por conductores
contratados. Los mantenimientos, documentos, inspecciones y novedades se manejan de forma manual
o no se registran. **Mi Flota** digitaliza ese control: cada conductor registra su servicio y las
novedades del vehículo, y los administradores reciben alertas, autorizan y consultan la hoja de vida
completa de cada vehículo.

El sistema está diseñado para crecer (más vehículos y conductores sin tocar código) y para servir
como evidencia ante el **PESV (Resolución 40595/2022)**, con miras a **ISO 39001**.

**Resultado esperado:** que ninguna novedad quede sin registrar, que ningún vehículo salga con una
falla crítica sin autorización trazable, y que la documentación no venza sin aviso.

---

## 2. Problema y objetivo

**Problema:** no hay control sistemático. Se desconoce el estado real de cada vehículo, no hay
historial, los vencimientos se descubren tarde y las novedades se pierden en conversaciones.

**Objetivos:**
1. Registrar el servicio diario de cada vehículo (inicio, ruta, inspección, cierre).
2. Reportar novedades con evidencia y darles seguimiento hasta cerrarlas.
3. Bloquear la operación ante fallas críticas y dejar trazabilidad de quién autorizó y por qué.
4. Controlar documentos y vencimientos.
5. Programar y registrar mantenimientos.
6. Consultar la hoja de vida completa por placa.

---

## 3. Alcance

**Incluido:** vehículos, conductores, documentos, inspecciones, novedades, autorizaciones,
servicios, mantenimiento, incidentes, hoja de vida, panel, notificaciones y auditoría.

**Excluido (otro producto):** facturación, nómina, combustible, GPS en tiempo real, contabilidad,
inteligencia artificial.

---

## 4. Usuarios y permisos

| Rol | Qué hace |
|---|---|
| **Conductor** | Ve solo su vehículo. Inicia y cierra servicio, hace la inspección, reporta novedades. Sin indicadores ni documentos ajenos. |
| **Administrador (2)** | Bandeja de novedades, gestión, cambio de vehículo, escalamiento, documentos, mantenimiento, incidentes, reportes, hoja de vida. **No** autoriza salidas con falla ni edita maestros. |
| **Superadministrador** | Todo lo anterior + maestros (vehículos, conductores, usuarios, plantillas) + **autorizar salida con falla** + auditoría. |

**Alta de administradores:** la hace el superadmin y en el mismo formulario se cargan sus
credenciales de notificación (correo y Telegram).

---

## 5. Flujos

### 5.1 Conductor

1. Entra con documento y contraseña.
2. Ves su vehículo asignado y su estado (operativo o bloqueado con motivo).
3. **Inicia servicio:** kilometraje inicial + **descripción corta de la operación**
   (ejemplo: "ARA del Codito").
4. **Inspección rápida** (solo ítems críticos, ~2 minutos):
   - todo en buen estado → puede salir;
   - algún ítem mal → foto obligatoria + informe → se crea **novedad**;
   - si el ítem es crítico → el vehículo se **bloquea** y se notifica.
5. Confirma la inspección con su **PIN/contraseña** (firma del conductor).
6. Durante la ruta puede **reportar novedad** (foto obligatoria).
7. **Cierra servicio:** kilometraje final y ¿hubo novedad?

### 5.2 Administrador

1. Recibe la novedad por los 4 canales.
2. Ve el temporizador de **15 minutos**.
3. Puede: dejar constancia de la gestión, **cambiar el vehículo** del conductor o **escalar** al superadmin.
4. No puede autorizar una salida con falla.
5. Valida la solución cuando el taller o el conductor la reportan.
6. Consulta vencimientos y hoja de vida.

### 5.3 Superadministrador

1. Recibe la solicitud de autorización.
2. Decide: mantener bloqueado, cambiar vehículo o **autorizar salida con falla**.
3. Para autorizar debe: escribir justificación, **reingresar su contraseña** y aceptar responsabilidad.
4. El sistema guarda usuario, fecha/hora, IP y **hash** de la justificación.
5. El viaje queda marcado con **sello rojo** en reportes.

---

## 6. Módulos por versión

### v0.1 — Entorno *(completada)*
Proyecto Django, usuario con roles, configuración por `.env`, pruebas, Git.

### v0.2 — Modelos de flota
Vehículo, Conductor, Documento, Configuración. Carga de la flota inicial. Migración a PostgreSQL.

### v0.3 — Acceso
Login, logout, permisos por rol, plantilla base de la interfaz.

### v0.4 — Maestros *(completada)*
CRUD de vehículos, conductores, usuarios y plantillas. Alta de administradores con correo y Telegram.

### v0.5 — Servicio *(completada)*
Inicio (km + ruta) y cierre (km + novedad), con todas sus reglas. Incluye la asignación de vehículo
con historial (`Asignacion`), que hace el administrador o el superadministrador.

### v0.6 — Inspección rápida
Plantilla, ítems, formulario móvil, fotos comprimidas, PIN de confirmación, detección de inspecciones sospechosas.

### v0.7 — Novedades
Creación desde inspección, ruta y cierre; severidad; ciclo de estados; bloqueo; bandeja con temporizador.

### v0.8 — Autorización
Pantalla del superadmin, firma de responsabilidad, sello rojo, auditoría.

### v0.9 — Documentos
Semáforo de 30/15/7/3/0 días, renovación, alertas.

### v0.10 — Hoja de vida y panel
Vista 360° por placa e indicadores (cumplimiento, bloqueos, fallas repetidas).

### v1.0 — Notificaciones y despliegue
Los 4 canales, reintentos, preferencias y puesta en producción.

### v1.1 — Mantenimiento e incidentes
Inspección profunda semanal, mantenimiento **registrado a mano** (tipo, fecha, km del vehículo y
km del próximo cambio, con aviso por distancia), incidentes, novedad → orden de trabajo.

### v1.2 — PESV y modo sin conexión
Capacitaciones, programas de riesgo, exámenes médicos, exportes PDF/Excel, PWA offline, foto georreferenciada.

### v2.0 — Escala
Multi-sede, API para terceros, integración con GPS/telemetría, app nativa si se justifica.

---

## 7. Reglas de negocio (definitivas)

| # | Regla |
|---|---|
| R1 | Un vehículo no puede tener dos servicios abiertos. |
| R2 | No se inicia servicio con el vehículo bloqueado. |
| R3 | No se inicia servicio sin la inspección rápida del día aprobada. |
| R4 | El cierre de servicio **siempre** se permite. |
| R5 | Foto obligatoria cuando el estado del ítem no es "buen estado". |
| R6 | La inspección se confirma con la contraseña del conductor. |
| R7 | Una novedad crítica bloquea el vehículo hasta ser validada. |
| R8 | Solo el superadmin autoriza salida con falla, con justificación, contraseña y aceptación. |
| R9 | El administrador solo puede cambiar de vehículo, escalar o dejar constancia. |
| R10 | El temporizador de autorización es de **15 minutos** (configurable). |
| R11 | Un documento vencido bloquea el vehículo (solo documentos del vehículo; la licencia del conductor se rige por R21). |
| R12 | El kilometraje nunca puede disminuir. |
| R13 | Toda acción queda auditada. |
| R14 | Nada se borra: retención mínima de 5 años. |
| R15 | Las notificaciones críticas no se pueden silenciar. |
| R16 | El mantenimiento se registra **a mano**: tipo, fecha, km del vehículo en ese momento y km del próximo cambio. El sistema calcula y muestra la distancia restante y avisa antes del vencimiento; **no** deduce intervalos por marca ni por referencia. |
| R17 | Validaciones del mantenimiento: el km del próximo cambio debe ser mayor que el km registrado, la fecha no puede ser futura y el km registrado no puede ser menor que el último kilometraje conocido del vehículo. |
| R18 | Toda asignación vehículo-conductor queda registrada y es consultable **al menos 2 años**. La hoja de vida muestra las más recientes paginadas (5 por página); lo no mostrado sigue guardado y nada se borra (R14). |
| R19 | Todo documento debe tener **soporte digital** (foto o PDF) para considerarse **completo**. Puede registrarse sin él: queda como **«soporte pendiente»** hasta que se suba desde el PC, sin duplicar la imagen en otra tabla (actualizada 2026-11-15). |
| R20 | **Dar de baja a un conductor** no borra nada: lo marca inactivo, registra fecha y motivo, cierra su asignación vigente y retira sus documentos de los vencimientos activos. Su historial sigue visible. |
| R21 | Una **licencia vencida o ausente** no bloquea el vehículo, pero impide que ese conductor inicie servicio. |

---

## 8. Modelo de datos (resumen)

Las entidades y campos están en `docs/CONTRATO_FRONT_BACK.md`, sección 7. Reglas de diseño:

- `Usuario` personalizado con `documento` como credencial (definido en v0.1).
- El estado del vehículo es **calculado**, no un campo editable.
- Toda tabla lleva `creado_en`, `creado_por`, `actualizado_en`.
- Índices en placa, documento, fecha de vencimiento y estado.
- `Asignación` guarda historial: quién autorizó un cambio y por qué.

---

## 9. Notificaciones

Cuatro canales, todos registrados en la tabla `Notificacion`:

| Canal | Requisito | Uso |
|---|---|---|
| En la app | — | Siempre; badge y bandeja |
| Correo | SMTP (cuenta Gmail de la empresa) | Respaldo y resumen diario |
| Telegram | Bot + chat_id por usuario | Urgencias |
| Web Push | Claves VAPID + service worker + HTTPS | Urgencias en el celular |

**Escalamiento:** crítica → los 4 canales y repetición a los 5 minutos si nadie la abre.
**Resumen diario:** 7:00 a. m. con vencimientos y pendientes.
**Reintentos:** 3 intentos por canal con espera creciente; el fallo queda registrado con su error.

> El **grupo de Telegram** de participantes es independiente del **bot** de alertas. El grupo es
> para comunicación humana; el bot es para eventos del sistema.

---

## 10. Interfaces

| Interfaz | Dispositivo | Características |
|---|---|---|
| **Conductor** | Celular (PWA instalable) | Una mano, botones grandes, 3 acciones principales, sin indicadores |
| **Admin / Superadmin** | PC y celular | Barra lateral, tablas con filtros, panel de alertas; en celular las tablas se vuelven tarjetas |

**Identidad visual:** verde `#1b8a3e`, verde oscuro `#116327`, crema `#fef7e5`, marrón `#3e110d`,
amarillo `#f7d117`, rojo alerta `#d93838`, tipografía Nunito.

---

## 11. Arquitectura técnica

- **Python 3.14.7 + Django 6.1.3**
- **PostgreSQL 18** (producción y desarrollo; SQLite solo como respaldo temporal)
- **HTML + CSS propio + HTMX** (sin SPA, sin React)
- **pytest + pytest-django** para pruebas; **ruff** para estilo
- **Git** para versiones
- Estructura: `config/`, `apps/`, `templates/`, `static/`, `tests/`, `docs/`

**Seguridad:** secretos en `.env`, contraseñas con hash, CSRF activo, sesiones con cookie,
permisos validados en el servidor, bloqueo por intentos fallidos (v1.1), HTTPS en producción.

---

## 12. Cambios respecto a los documentos originales

| Tema | Documento original decía | Ahora | Motivo |
|---|---|---|---|
| Tiempo de autorización | 15 min y 5 min (contradicción) | **15 min**, configurable | Realismo operativo |
| Quién autoriza | Admin con justificación / solo superadmin | **Solo superadmin** | El Anexo 2.0 sustituye el punto 7.2; protección legal |
| Firma | "Firma digital" | **Firma de responsabilidad electrónica** | "Firma digital" exige certificado (Ley 527) |
| Maestros | Admin los gestiona / solo superadmin | **Solo superadmin** | Separación de funciones |
| Foto | Obligatoria solo si "deteriorado" | **Siempre que no sea "buen estado"** | La ausencia también debe probarse |
| Fin de ruta | Bloqueado con novedades críticas | **Siempre permitido** | El bloqueo protege la salida, no el regreso |
| Inspección | Una sola / rápida + profunda | **Rápida diaria y profunda semanal** | Cumple el Anexo 3.2 |
| Ítems | Adaptados por vehículo | **Plantilla maestra** + copia por vehículo | Simplicidad y orden |
| Estados | Bloqueado / inhabilitado / requiere cambio | **6 estados calculados** | Una sola fuente de verdad |
| Notificaciones | Push sin definir | **4 canales con registro y reintentos** | Que nunca se pierda una alerta |
| Stack | Django + DRF + JWT + PWA React | **Django + plantillas + HTMX + sesiones** | Menos capas, más seguridad, mismo resultado |
| Alcance | 10 módulos de golpe | **Versiones v0.1 → v2.0** | Entregas verificables |
| Flota | "7 vehículos" fijo | **Escalable sin tocar código** | Crecimiento de la empresa |
| Inicio de servicio | No existía | **Nuevo, con ruta/operación** | Sin inicio no hay control de turno |
| Cálculo de mantenimiento | Automático por marca y referencia | **Manual**: el usuario digita fecha, km del vehículo y km del próximo cambio | No hay planes de mantenimiento por marca cargados; se evita depender de datos que la empresa no tiene |
| Campos del mantenimiento | `tipo` era el catálogo de servicios | **`tipo`** (preventivo/correctivo), **`servicio`** (qué se hizo) y **`parte`** (dónde) | Un cambio de aceite puede ser preventivo o correctivo; son tres datos distintos (decidido con las maquetas del 13/11) |
| Factura del mantenimiento | No existía | **Opcional**, con soporte adjunto y estado `pendiente`/`adjunta` | Respaldo contable y trazabilidad del gasto |
| Historial de conductores | Sin regla | Consultable **al menos 2 años**, paginado de 5 en 5 | Regla del dueño (13/11); lo que no se muestra sigue guardado (R14) |
| Baja de conductor | No existía | Marca inactivo, cierra asignación y retira sus documentos activos, sin borrar historial | Un retiro no puede dejar documentos "vigentes" ni perder trazabilidad |
| Licencia del conductor | "Documento vencido bloquea el vehículo" | Bloquea al **conductor**, no al vehículo | La licencia no es un documento del vehículo (R21) |
| Soporte de documentos | No se exigía | **Obligatorio** (foto o PDF) para contar como válido | El PESV exige evidencia, no solo el dato |

---

## 13. Estado actual (fin de la sesión 2026-11-09)

**Completado — v0.1:**
- Entorno virtual con Python 3.14.7 y Django 6.1.3.
- Proyecto `config` y app `apps/usuarios` con usuario personalizado y roles.
- Configuración por `.env`, `.gitignore`, `README.md`, `pytest.ini`, `pyproject.toml`.
- Página de verificación en `/` y panel de Django en `/admin/`.
- Repositorio Git inicializado (sin commit todavía).
- Renombres de archivos con errores de tipeo.

**Verificado:** `manage.py check` sin problemas · 14 migraciones aplicadas · 2 pruebas pasan ·
`ruff` sin errores · `.env` correctamente ignorado por Git.

**Pendiente inmediato (v0.2):**
1. Crear base de datos y usuario en PostgreSQL 18.
2. Cambiar `DB_ENGINE=postgresql` en `.env` y migrar.
3. Modelos `Vehiculo`, `Conductor`, `Documento`, `Configuracion`.
4. Cargar los datos reales de la flota.
5. Primer commit.

### Estado al 2026-11-15

- **v0.1** sigue completada y verificada; el repositorio es la carpeta `App\` de este proyecto.
- **Maquetas del encargo 01 validadas** (4 pantallas, 9 archivos): cumplen los 9 criterios técnicos del
  encargo. Viven solo en el respaldo local del disco de trabajo (`Avances\maquetas`) y **no** se han
  integrado al repositorio: llevan incrustado el logo real de la empresa y el repositorio es público.
- **Contrato alineado** con las decisiones de las maquetas: `tipo`/`servicio`/`parte`, factura del
  mantenimiento, baja de conductor, soporte documental y reglas R18 a R21.
- **Siguiente:** decidir si primero se completan las pantallas que pidió el dueño el 13/11
  (reportar novedad, gestionar novedad, vehículos, conductores) o si se abre v0.2 con los modelos.

### Estado al 2026-11-15 (cierre de la sesión de la tarde)

- **v0.2 completada:** modelos de flota + admin + PostgreSQL, con 5 vehículos y 14 documentos reales
  cargados (todos con «soporte pendiente», R19).
- **v0.3 avanzada:** `static/css/mi-flota.css` con la paleta de las maquetas, `templates/base.html`
  con sidebar vinotinto y logo neutro «MF», login por cédula en `/cuenta/login/`, y las pantallas
  `flota/` (vehículos), `flota/vehiculos/<placa>/` (hoja de vida con semáforo documental y 6 espacios
  de foto) y `flota/documentos/` con filtro «solo soporte pendiente».
- **Permisos por rol activos:** anónimo → login; conductor → aviso de que su pantalla llega en v0.5;
  admin y superadmin → flota. 46 pruebas pasan, `ruff` limpio, sin migraciones pendientes.
- **Encargo 02 entregado al agente de diseño** con plan de 4 días (16 al 19/11/2026): galería de
  fotos, documentos y visor, conductores y baja, y novedades/vehículos/factura.

### Estado al 2026-11-15 (v0.5)

- **v0.5 completada:** el conductor ya tiene pantalla propia en `/conductor/` («Mi servicio»), inicia
  con kilometraje y ruta en `/servicio/iniciar/` y cierra en `/servicio/<id>/cerrar/` con km final y
  novedad opcional («sin novedad» por defecto). El cierre siempre se permite; el bloqueo por
  documento vencido (R11) o licencia vencida (R21) se evalúa al iniciar.
- **Asignación con historial:** modelo `Asignacion` (vehículo, conductor, fecha de inicio y fin,
  motivo y quién la creó). Solo el administrador o el superadministrador asigna desde la lista de
  conductores; el conductor no puede asignarse ni cambiarse de vehículo.
- **La inspección rápida todavía no bloquea:** llega en la v0.6 como paso obligatorio.
- **78 pruebas** pasan, `ruff` limpio, sin migraciones pendientes (`flota.0005`).
- **Siguiente:** integrar los Días 1 y 2 del encargo 02 (galería de 6 fotos y visor de soportes) y
  después la v0.6 (inspección rápida).

---

## 14. Riesgos y pendientes

| Riesgo / pendiente | Impacto | Mitigación |
|---|---|---|
| Solo hay datos de 5 de los 7 vehículos | El sistema arranca incompleto | El usuario está recopilando los 2 restantes y los datos de los conductores |
| Licencia de ejemplo vencida | El conductor de prueba no puede iniciar servicio | Se reemplaza con datos reales |
| Web Push limitado en iPhone | Un canal menos en iOS | Requiere instalar la PWA (iOS 16.4+); correo y Telegram cubren |
| Sin conexión en zona rural | Inspecciones perdidas | Modo offline en v1.2 |
| Fotos de 2–4 MB | Consumo de datos | Compresión a ≤1 MB antes de subir |
| Datos personales de conductores | Ley 1581/2012 | Consentimiento informado y acceso restringido |
| Servidor de producción | Caída del servicio | VPS + respaldos diarios (v1.0) |

---

## 15. Plan de aprendizaje

Cada versión incluye: **lo que construyo yo**, **lo que haces tú** (ejercicio verificable) y
**lo que aprendes** (concepto). El detalle está en la conversación de cada sesión y se resume en
`MEMORY.md`.

Regla de trabajo: una versión a la vez, con pruebas que pasan antes de avanzar.

---

## 16. Glosario

| Término | Significado |
|---|---|
| **PESV** | Plan Estratégico de Seguridad Vial (obligatorio en Colombia) |
| **Preoperacional** | Revisión del vehículo antes de salir a operar |
| **Novedad** | Problema o hallazgo reportado sobre un vehículo |
| **Novedad crítica** | La que impide operar con seguridad (frenos, fugas, extintor ausente, documento vencido) |
| **Hoja de vida** | Historial completo de un vehículo |
| **Sello rojo** | Marca en reportes de un viaje autorizado pese a una falla crítica |
| **Migración** | Archivo que aplica un cambio de estructura a la base de datos |
| **Entorno virtual** | Carpeta aislada con las librerías del proyecto |
| **PWA** | Aplicación web instalable en el celular |
| **VAPID** | Claves que permiten enviar notificaciones Web Push |
| **Webhook / Bot** | Programa que envía mensajes automáticos a Telegram |
