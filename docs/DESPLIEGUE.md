# Despliegue de la v1.0 (24/7)

Estado: **opción A elegida por el dueño el 25/11/2026**. Dependencias ya instaladas y
verificadas; falta el dominio y el túnel con nombre.

**Recomendación para hacerlo de la mejor manera:**
1. Comprar un dominio propio barato (Cloudflare Registrar o Namecheap, unos USD 10/año) y usar
   `miflota.<tu-dominio>`. Es estable, profesional y evita depender de una URL aleatoria.
2. Crear un **túnel con nombre** de Cloudflare (no el túnel rápido): el túnel rápido cambia de
   dirección cada vez que se reinicia y solo sirve para una primera prueba.
3. Activar **Cloudflare Access** con correo o PIN para que, además del login de Django, haya
   una segunda barrera antes de llegar al sitio.
4. Configurar el PC para que **no entre en suspensión** y, si es posible, con UPS: el 24/7
   depende de esa máquina.
5. Programar copias diarias de PostgreSQL (o copiar el archivo de la base a la USB `F:`).

El `chat_id` del superadministrador ya quedó guardado en la base real; la enseñanza de las dos
vías queda pendiente (#41) a petición del dueño.

## 1. Prueba previa (ya completada)

Antes de publicar se creó un aviso de prueba en la base real, solo para el superadministrador
y solo por los canales **app** y **correo**:

- `enviar_notificaciones` → **2 enviadas, 0 errores**.
- Bandeja `/notificaciones/` → HTTP 200; detalle `/notificaciones/1/` → HTTP 200.
- El canal app queda visible en la bandeja; el correo sale por el SMTP real.

Telegram y Web Push **no** se probaron de extremo a extremo. El `chat_id` del superadministrador
ya quedó guardado en la base real (25/11), pero falta activar una suscripción en un navegador.
Por eso Web Push seguirá marcando error hasta que se configure. Las notificaciones críticas no
se pueden silenciar (R15), así que seguirán intentando los 4 canales.

## 2. Qué significa 24/7

El programa debe ejecutarse en una máquina que esté siempre encendida. En este PC las tareas
`MiFlota-*` funcionan, pero se detienen si apagas la computadora. Hay tres caminos:

| Opción | Descripción | Ideal cuando |
|---|---|---|
| **A (recomendada para empezar)** | El PC sigue ejecutando el programa; un túnel de Cloudflare le da HTTPS y una dirección pública sin abrir puertos | Quieres arrancar hoy sin alquilar servidor y aceptas que el PC esté encendido |
| **B** | Servidor pequeño alquilado (VPS) con Python, PostgreSQL y nginx | Quieres disponibilidad real 24/7 y control total |
| **C** | Plataforma administrada (Render/Railway) | No quieres administrar sistema, aceptas pagar mensualidad |

## 3. Plan para la opción A (PC + Cloudflare Tunnel)

1. **Servidor de aplicación.** Instalar en el entorno virtual:
   - `waitress` (servidor WSGI para producción, reemplaza a `runserver`).
   - `whitenoise` (sirve CSS, JS, `sw.js` y el manifiesto sin nginx).
   Arranque: `waitress-serve --host=127.0.0.1 --port=8000 config.wsgi:application`.

2. **Dominio y túnel.**
   - Crear cuenta en Cloudflare y añadir un dominio.
   - Instalar `cloudflared` y crear un túnel: `cloudflared tunnel create miflota`.
   - Configurar `config.yml` con `ingress` → `http://127.0.0.1:8000`.
   - Crear el registro DNS CNAME que Cloudflare indica.
   - Ejecutar el túnel como servicio de Windows para que arranque solo.

3. **Seguridad Django.**
   - `DEBUG=False` en el `.env` del servidor.
   - `ALLOWED_HOSTS` con el dominio del túnel.
   - `CSRF_TRUSTED_ORIGINS` con `https://<dominio>`.
   - `SECRET_KEY` propia, creada en el servidor. **No copiar el `.env` de este PC.**

4. **Archivos estáticos.** `python manage.py collectstatic` y activar WhiteNoise en
   `MIDDLEWARE` y `STATIC_ROOT`.

5. **Base de datos.** PostgreSQL 18 ya está en este PC; si el programa sigue aquí no hay que
   moverla. Solo verificar backups automáticos.

6. **Tareas.** Registrar de nuevo las tres tareas `MiFlota-*` con el script
   `scripts\registrar_tareas_notificaciones.ps1`; en este PC ya están listas.

7. **Verificación final.**
   - Abrir `https://<dominio>/` y entrar con el superusuario.
   - Revisar `/notificaciones/`.
   - Enviar `manage.py comprobar_correo` y `manage.py comprobar_telegram --sin-envio`.
   - Desde el celular, abrir el sitio, ir a preferencias y activar Web Push.

## 4. Dependencias instaladas y verificadas

El dueño autorizó la instalación el 25/11. Quedaron fijadas en `requirements.txt`:

```text
waitress==3.0.2
whitenoise==6.12.0
```

WhiteNoise quedó en `MIDDLEWARE` y `collectstatic` ya se ejecutó (134 archivos). Prueba real
con `waitress-serve --host=127.0.0.1 --port=8020 config.wsgi:application`: HTTP 200 en `/`,
`/static/css/mi-flota.css`, `/static/manifest.webmanifest`, `/sw.js` y `/notificaciones/`.

## 5. Estado de las decisiones

1. ✅ Opción A elegida por el dueño.
2. ✅ Instalación de `waitress` y `whitenoise` autorizada y ejecutada.
3. ✅ `chat_id` guardado en la base real; la enseñanza sigue pospuesta (#41).
4. ⏳ Falta: crear cuenta de Cloudflare, elegir/comprar dominio y crear el túnel con nombre.
5. ⏳ Falta: decidir si se activa Cloudflare Access (recomendado) y configurar el PC sin suspensión.
