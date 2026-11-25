/* Service worker de Mi Flota: recibe Web Push con la pestaña cerrada. */
self.addEventListener("push", function (event) {
  var datos = {};
  if (event.data) {
    try {
      datos = event.data.json();
    } catch (error) {
      datos = { mensaje: event.data.text() };
    }
  }
  event.waitUntil(
    self.registration.showNotification(datos.titulo || "Mi Flota", {
      body: datos.mensaje || "Tienes un aviso nuevo.",
      data: { url: datos.url || "/notificaciones/" },
      tag: datos.evento || "mi-flota",
    })
  );
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  var destino = (event.notification.data && event.notification.data.url) || "/notificaciones/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (ventanas) {
      for (var i = 0; i < ventanas.length; i += 1) {
        if (ventanas[i].url.indexOf(destino) !== -1) {
          return ventanas[i].focus();
        }
      }
      return self.clients.openWindow(destino);
    })
  );
});
