/* Registro del service worker y suscripción Web Push (v1.0). */
(function () {
  "use strict";

  function byteArrayDeClave(claveBase64Url) {
    var relleno = "=".repeat((4 - (claveBase64Url.length % 4)) % 4);
    var base64 = (claveBase64Url + relleno).replace(/-/g, "+").replace(/_/g, "/");
    var binario = atob(base64);
    var salida = new Uint8Array(binario.length);
    for (var i = 0; i < binario.length; i += 1) {
      salida[i] = binario.charCodeAt(i);
    }
    return salida;
  }

  function tokenCsrf() {
    var partes = document.cookie.split(";");
    for (var i = 0; i < partes.length; i += 1) {
      var parte = partes[i].trim();
      if (parte.indexOf("csrftoken=") === 0) {
        return decodeURIComponent(parte.substring("csrftoken=".length));
      }
    }
    return "";
  }

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () {
        // Sin service worker la app sigue funcionando: solo se pierde Web Push.
      });
    });
  }

  var boton = document.getElementById("activar-push");
  var estado = document.getElementById("estado-push");
  if (!boton) {
    return;
  }

  boton.addEventListener("click", async function () {
    if (!("Notification" in window) || !("serviceWorker" in navigator)) {
      estado.textContent = "Este navegador no admite notificaciones push.";
      return;
    }
    var clave = boton.dataset.vapid || "";
    if (!clave) {
      estado.textContent = "Faltan las claves VAPID en el servidor.";
      return;
    }
    var permiso = await Notification.requestPermission();
    if (permiso !== "granted") {
      estado.textContent = "Permiso no concedido. No se guardó ninguna suscripción.";
      return;
    }
    try {
      var registro = await navigator.serviceWorker.ready;
      var suscripcion = await registro.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: byteArrayDeClave(clave),
      });
      var respuesta = await fetch("/notificaciones/suscribir/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": tokenCsrf(),
        },
        body: JSON.stringify(suscripcion.toJSON()),
      });
      estado.textContent = respuesta.ok
        ? "Avisos activados en este navegador."
        : "No se pudo guardar la suscripción (HTTP " + respuesta.status + ").";
    } catch (error) {
      estado.textContent = "No se pudo activar: " + error.message;
    }
  });
})();
