"""Rutas de datos maestros (contrato §5.3)."""

from django.urls import path

from . import views

app_name = "maestros"

urlpatterns = [
    path("vehiculos/nuevo/", views.VehiculoCrearView.as_view(), name="vehiculo_nuevo"),
    path(
        "vehiculos/<str:placa>/editar/",
        views.VehiculoEditarView.as_view(),
        name="vehiculo_editar",
    ),
    path("conductores/nuevo/", views.ConductorCrearView.as_view(), name="conductor_nuevo"),
    path(
        "conductores/<int:pk>/editar/",
        views.ConductorEditarView.as_view(),
        name="conductor_editar",
    ),
    path(
        "conductores/<int:pk>/baja/",
        views.ConductorBajaView.as_view(),
        name="conductor_baja",
    ),
    path("usuarios/", views.UsuarioListaView.as_view(), name="usuario_lista"),
    path("usuarios/nuevo/", views.UsuarioCrearView.as_view(), name="usuario_nuevo"),
    path(
        "usuarios/<int:pk>/editar/",
        views.UsuarioEditarView.as_view(),
        name="usuario_editar",
    ),
]
