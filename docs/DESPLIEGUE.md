# Despliegue de la v1.0 (24/7)

Estado: **plan preparado el 25/11/2026, sin ejecutar**. Requiere decisión del dueño sobre dónde
vivirá el programa y autorización para instalar dos dependencias nuevas.

## 1. Prueba previa (ya completada)

Antes de publicar se creó un aviso de prueba en la base real, solo para el superadministrador
y solo por los canales **app** y **correo**:

- `enviar_notificaciones` → **2 enviadas, 0 errores**.
- Bandeja `/notificaciones/` → HTTP 200; detalle `/notificaciones/1/` → HTTP 200.
- El canal app queda visible en la bandeja; el correo sale por el SMTP real.

Telegram y Web Push **no** se probaron de extremo a extremo: falta guardar el `chat_id` del
usuario y activar una suscripción en un navegador. Por eso, al desplegar, esos dos canales
seguirán marcando error hasta que se configuren. Las notificaciones críticas no se pueden
silenciar (R15), así que seguirán intentando los 4 canales.

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

## 4. Dependencias que faltan (requieren autorización)

```text
waitress==3.x
whitenoise==6.x
```

Se fijarán en `requirements.txt` después de instalarlas y comprobar la versión exacta.

## 5. Decisiones pendientes del dueño

1. Elegir opción A, B o C.
2. Autorizar la instalación de `waitress` y `whitenoise`.
3. Indicar el dominio a usar (o aceptar un subdominio gratuito de túnel para la primera prueba).
4. Decidir cuándo enseñar/guardar el `chat_id` (pendiente #41, pospuesto por ahora).
