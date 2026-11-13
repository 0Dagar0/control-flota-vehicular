# Contrato Frontend ↔ Backend — Mi Flota

**Versión:** 2.0 (definitiva)
**Fecha:** 2026-11-09
**Reemplaza a:** `Contrato Front Back.rtf` (v1.0 + Anexo 2.0)

Este documento define **cómo se comunican las pantallas con el servidor**.
Toda pantalla y toda regla debe respetarlo. Si algo no está aquí, no se implementa.

---

## 1. Principios generales

1. **La lógica vive en el servidor.** El navegador solo muestra y envía datos. Ninguna regla de negocio (bloqueos, permisos, cálculos) se valida solo en el frontend.
2. **Una sola fuente de verdad:** la base de datos. El estado de un vehículo se **calcula**, no se escribe a mano.
3. **Todo cambio queda auditado:** usuario, fecha/hora, IP y valores antes/después.
4. **Fechas:** se guardan en UTC (ISO 8601) y se muestran en hora de Colombia (`America/Bogota`).
5. **Nada se borra.** Los registros son inmutables; se corrigen agregando un registro nuevo y quedan auditados (Resolución 40595/2022, retención mínima 5 años).
6. **Secretos fuera del código:** claves en `.env`, nunca en plantillas ni en Git.

---

## 2. Dos capas de comunicación

| Capa | Uso | Formato |
|---|---|---|
| **A. Web (HTML)** | Pantallas del conductor, admin y superadmin | Formularios HTML + fragmentos HTMX |
| **B. API JSON** | Sincronización de la PWA sin señal y futuras apps | JSON en `/api/v1/` |

La capa A es la principal. La capa B existe para que la app funcione sin internet y para no cerrar la puerta a una app móvil nativa.

---

## 3. Autenticación y sesión

- **Web:** sesión con cookie (`HttpOnly`, `Secure` en producción) + token CSRF en cada formulario.
- **API:** token Bearer (se implementa en v1.2 junto con el modo sin conexión).
- El identificador de acceso es el **documento**, no un nombre de usuario.
- Contraseña mínimo 10 caracteres, guardada como hash (nunca en texto plano).
- Sesión inactiva: 8 horas. En dispositivos del conductor: 12 horas.

### 3.1 Endpoints de acceso

| Método | Ruta | Descripción |
|---|---|---|
| `GET/POST` | `/acceso/` | Iniciar sesión |
| `POST` | `/salida/` | Cerrar sesión |
| `GET/POST` | `/mi-clave/` | Cambiar contraseña |

**Errores de acceso:** mensaje genérico "Documento o contraseña incorrectos" (no revelar cuál falló).

---

## 4. Roles y permisos

| Acción | Conductor | Admin | Superadmin |
|---|---|---|---|
| Iniciar / cerrar servicio | ✅ (su vehículo) | — | — |
| Registrar inspección | ✅ (su vehículo) | — | — |
| Reportar novedad | ✅ | — | — |
| Ver bandeja de novedades | — | ✅ | ✅ |
| Gestionar novedad (nota / cambio de vehículo / escalar) | — | ✅ | ✅ |
| **Autorizar salida con falla** | — | ❌ | ✅ |
| Ver hoja de vida de cualquier vehículo | — | ✅ | ✅ |
| Ver documentos y vencimientos | — | ✅ | ✅ |
| Registrar mantenimiento e incidentes | — | ✅ | ✅ |
| Crear/editar vehículos, conductores, usuarios, plantillas | — | ❌ | ✅ |
| Editar un registro original | — | ❌ | ✅ |
| Ver auditoría | — | — | ✅ |

**Regla dura:** si un conductor intenta acceder a una ruta de administración, el servidor responde **403** aunque conozca la URL.

---

## 5. Capa A — Rutas web

### 5.1 Conductor

| Método | Ruta | Entrada | Salida |
|---|---|---|---|
| `GET` | `/conductor/` | — | Pantalla de inicio con vehículo asignado y estado |
| `GET` | `/servicio/iniciar/` | — | Formulario: km inicial, ruta/operación |
| `POST` | `/servicio/iniciar/` | `kilometraje_inicial`, `descripcion_ruta` | Redirige a inspección rápida |
| `GET` | `/inspeccion/rapida/<placa>/` | — | Lista de ítems críticos |
| `POST` | `/inspeccion/rapida/<placa>/` | `items[]`, `firma_pin` | Guarda y calcula bloqueo |
| `GET/POST` | `/novedades/nueva/` | `descripcion`, `severidad`, `foto[]` | Crea novedad |
| `POST` | `/servicio/<id>/cerrar/` | `kilometraje_final`, `tuvo_novedad` | Cierra el servicio |
| `GET` | `/mis-novedades/` | — | Novedades propias y su estado |

**Validaciones obligatorias (servidor):**

- No se inicia servicio si: el vehículo está bloqueado, ya tiene un servicio abierto, o no tiene inspección rápida del día aprobada.
- `kilometraje_inicial` ≥ último kilometraje registrado.
- `descripcion_ruta` obligatoria, entre 5 y 120 caracteres.
- Foto obligatoria cuando el estado del ítem no es `buen_estado`.
- La inspección exige `firma_pin` (contraseña del conductor) para cerrarse.
- El cierre de servicio **siempre** se permite (el bloqueo aplica al siguiente inicio).

### 5.2 Administrador

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/panel/` | Indicadores: vehículos, bloqueados, novedades, cumplimiento |
| `GET` | `/novedades/` | Bandeja con filtros por estado, severidad y placa |
| `GET/POST` | `/novedades/<id>/gestion/` | Registrar gestión, cambiar vehículo o escalar |
| `GET` | `/vehiculos/` | Listado paginado |
| `GET` | `/vehiculos/<placa>/` | Hoja de vida resumida |
| `GET` | `/hoja-vida/<placa>/` | Vista 360°: documentos, inspecciones, novedades, mantenimientos, incidentes |
| `GET/POST` | `/documentos/` | Registrar o renovar documentos |
| `GET/POST` | `/mantenimientos/` | Registrar mantenimiento manual: tipo, fecha, km, próximo km (v1.1) |
| `GET/POST` | `/incidentes/` | Registrar accidente o incidente (v1.1) |
| `GET` | `/reportes/` | Cumplimiento, fallas repetidas, bloqueos |

### 5.3 Superadministrador

| Método | Ruta | Descripción |
|---|---|---|
| `GET/POST` | `/maestros/vehiculos/` | Crear y editar vehículos |
| `GET/POST` | `/maestros/conductores/` | Crear y editar conductores |
| `GET/POST` | `/maestros/usuarios/` | Crear administradores (correo y Telegram incluidos) |
| `GET/POST` | `/maestros/plantillas/` | Ítems de inspección, críticos y nivel |
| `POST` | `/novedades/<id>/autorizar/` | Autorizar salida con falla (firma de responsabilidad) |
| `GET` | `/auditoria/` | Registro de acciones |

**Firma de responsabilidad — campos obligatorios:**

| Campo | Validación |
|---|---|
| `justificacion` | 20 a 500 caracteres |
| `password` | Debe coincidir con la contraseña del superadmin |
| `acepta_responsabilidad` | Debe ser `true` |
| `hash_justificacion` | Se calcula en el servidor (SHA-256), no lo envía el cliente |

Si falta cualquiera de los tres primeros, se rechaza con **400**.

### 5.4 Mantenimiento (v1.1)

Registran el mantenimiento el **administrador** y el **superadministrador**. El cálculo es
**manual**: el sistema no deduce intervalos por marca ni por referencia (regla R16 del documento
maestro).

**Flujo en pantalla:**

1. Se elige el vehículo. El sistema muestra su `km_actual` como referencia.
2. El usuario confirma o corrige el **km que tenía el vehículo cuando se hizo** el mantenimiento.
3. Se piden la **fecha en que se realizó** y el **km en que se cumple el próximo cambio**.
4. Datos opcionales: próxima fecha, costo y observaciones.
5. Al guardar, la pantalla muestra **"faltan N km"** y avisa cuando la distancia restante baja del
   umbral configurado (por defecto **500 km**).

**Campos del formulario:**

| Campo | Obligatorio | Validación |
|---|---|---|
| `vehiculo` | Sí | Debe existir y no estar dado de baja |
| `tipo` | Sí | Catálogo: aceite, filtros, frenos, llantas, otro |
| `fecha` | Sí | No puede ser futura |
| `km` | Sí | Mayor o igual al último kilometraje registrado del vehículo (R12) |
| `proximo_km` | Sí | Mayor que `km` |
| `proxima_fecha` | No | Si viene, debe ser posterior a `fecha` |
| `costo` | No | Mayor o igual a 0 |
| `observaciones` | No | Máximo 500 caracteres |

Se rechaza con **400** cualquier combinación que incumpla las validaciones de `fecha`, `km` y
`proximo_km`. Ningún mantenimiento se borra: se corrige con otro registro y queda auditado.

---

## 6. Capa B — API JSON (`/api/v1/`)

### 6.1 Formato de respuesta

Éxito:

```json
{ "ok": true, "datos": { } }
```

Error:

```json
{
  "error": true,
  "codigo": "ERR_VALIDACION",
  "mensaje": "Descripción clara para el usuario",
  "detalles": { "campo": "motivo" }
}
```

### 6.2 Códigos HTTP

| Código | Cuándo |
|---|---|
| `200` | Consulta correcta |
| `201` | Recurso creado |
| `400` | Datos inválidos |
| `401` | No autenticado |
| `403` | Autenticado sin permiso |
| `404` | No existe |
| `409` | Conflicto (servicio ya abierto, placa duplicada) |
| `422` | Regla de negocio incumplida (vehículo bloqueado) |
| `500` | Error del servidor |

### 6.3 Endpoints

| Método | Ruta | Uso |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Devuelve `token` y datos del usuario |
| `GET` | `/api/v1/sincronizar?desde=` | Datos maestros desde una fecha (modo sin conexión) |
| `POST` | `/api/v1/uploads` | Sube una imagen y devuelve `url` |
| `POST` | `/api/v1/servicios/iniciar` | Inicia servicio |
| `POST` | `/api/v1/servicios/<id>/cerrar` | Cierra servicio |
| `GET` | `/api/v1/inspecciones/plantilla/<placa>` | Plantilla rápida o profunda (`?nivel=rapida`) |
| `POST` | `/api/v1/inspecciones` | Envía inspección (acepta lote desde la PWA) |
| `POST` | `/api/v1/novedades` | Crea novedad |
| `GET` | `/api/v1/novedades/pendientes` | Bandeja del administrador |
| `POST` | `/api/v1/novedades/<id>/gestionar` | Gestión del administrador |
| `POST` | `/api/v1/novedades/<id>/autorizar` | Autorización del superadmin |
| `GET` | `/api/v1/vehiculos/<placa>/historial` | Hoja de vida 360° |
| `GET` | `/api/v1/reportes/exportar-pesv` | Exporte para auditoría (v1.2) |

### 6.4 Reglas de la capa API

1. **Subida de archivos:** las imágenes nunca viajan dentro del JSON. Primero `POST /api/v1/uploads`, luego se envía la `url`.
2. **Imágenes:** máximo 3 por novedad, comprimidas a 1600 px de ancho y ≤ 1 MB.
3. **Sincronización:** cada registro enviado sin conexión lleva un `uuid_cliente`; si llega repetido, el servidor no duplica (idempotencia).
4. **Lote:** `POST /api/v1/inspecciones` acepta `items[]`; si un ítem falla, se rechaza todo el envío (transacción).

---

## 7. Modelo de datos (entidades y campos clave)

| Entidad | Campos principales |
|---|---|
| **Usuario** | documento (único), email (único), rol, teléfono, telegram_chat_id, activo |
| **Vehículo** | placa (única), marca, referencia, modelo, tipo_carrocería, VIN, motor, combustible, km_actual, propietario, estado_calculado |
| **Conductor** | usuario, licencia_categoría, licencia_vencimiento, contacto_emergencia |
| **Asignación** | vehículo, conductor, desde, hasta, autorizado_por, motivo |
| **Documento** | tipo, vehículo/conductor, aseguradora, número, vencimiento, soporte |
| **PlantillaInspección** | nombre, nivel (rápida/profunda), activa |
| **ItemInspección** | plantilla, grupo, nombre, es_critico, requiere_foto, orden |
| **Inspección** | vehículo, conductor, plantilla, fecha/hora, km, duración, firma, resultado |
| **RespuestaItem** | inspección, ítem, estado, informe, fotos |
| **Servicio** | vehículo, conductor, inicio, fin, km_inicial, km_final, descripcion_ruta, estado |
| **Novedad** | vehículo, conductor, origen, descripción, severidad, estado, requiere_superadmin |
| **Gestión** | novedad, usuario, descripción, fecha |
| **Autorización** | novedad, superadmin, justificación, hash, ip, fecha |
| **Mantenimiento** | vehículo, tipo, fecha, km, costo, próximo_km, próxima_fecha (opcional), observaciones (v1.1) |
| **Incidente** | vehículo, conductor, fecha, gravedad, descripción, causa, acción (v1.1) |
| **Notificación** | usuario, evento, canal, estado, intentos, error, enviado_en |
| **Auditoría** | usuario, acción, entidad, id, datos_antes, datos_despues, ip, fecha |

---

## 8. Estados

### 8.1 Novedad

```
ABIERTA → EN_PROCESO → RESUELTA → VALIDADA
   └──────────────→ RECHAZADA
```

- Crítica: agrega `requiere_superadmin = true` y bloquea el vehículo mientras no esté resuelta y validada.
- Cambios de estado permitidos solo por admin o superadmin, y quedan auditados.

### 8.2 Vehículo (calculado)

| Estado | Condición |
|---|---|
| `OPERATIVO` | Sin bloqueos, sin servicio abierto |
| `EN_SERVICIO` | Tiene un servicio abierto |
| `BLOQUEADO_NOVEDAD` | Tiene novedad crítica sin validar |
| `BLOQUEADO_DOCUMENTO` | SOAT, tecnomecánica o licencia vencidos |
| `EN_MANTENIMIENTO` | Mantenimiento abierto |
| `FUERA_DE_SERVICIO` | Baja definitiva |

---

## 9. Eventos que generan notificación

| Evento | Destinatarios | Canales |
|---|---|---|
| Novedad crítica | Admin + superadmin | App, correo, Telegram, Web Push |
| Solicitud de autorización | Superadmin | App, correo, Telegram, Web Push |
| Autorización concedida | Conductor + admins | App, correo |
| Documento a 7, 3 y 0 días | Admin + superadmin | App, correo (resumen diario 7:00 a. m.) |
| Inspección no realizada al mediodía | Admin | App |
| Servicio cerrado con novedad | Admin | App |
| Mantenimiento cerca del próximo cambio (umbral 500 km) | Admin + superadmin | App, correo (resumen diario) |

El escalamiento y los reintentos se definen en el documento maestro (sección 9).

---

## 10. Criterios de aceptación del contrato

1. Ninguna regla de la sección 5 se puede saltar llamando la API directamente.
2. Un conductor autenticado recibe 403 en cualquier ruta de administración.
3. Toda novedad crítica bloquea el inicio de servicio en menos de 1 segundo.
4. Toda autorización con falla queda con justificación, hash, usuario, IP y fecha.
5. Toda respuesta de error respeta el formato de la sección 6.1.
