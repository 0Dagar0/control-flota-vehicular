"""Pruebas de la galería de fotos del vehículo (pantalla de carga, v0.3+).

Cubre permisos, las 6 ranuras, la subida, el reemplazo con historial y el
rechazo de archivos que no son imágenes.
"""

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from apps.flota.models import FotoVehiculo, Vehiculo
from apps.usuarios.models import Usuario

CLAVE = "ClaveSegura2026"


def png_valido(lado=1):
    """PNG real generado con Pillow para que pase la validación del modelo."""
    buffer = BytesIO()
    Image.new("RGB", (lado, lado), "white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def admin(db):
    return Usuario.objects.create_user(
        documento="900100100",
        email="admin@ejemplo.com",
        password=CLAVE,
        first_name="Ana",
        last_name="Rojas",
        rol=Usuario.Rol.ADMIN,
    )


@pytest.fixture
def conductor(db):
    return Usuario.objects.create_user(
        documento="10203040",
        email="conductor@ejemplo.com",
        password=CLAVE,
        first_name="Carlos",
        last_name="Pérez",
        rol=Usuario.Rol.CONDUCTOR,
    )


@pytest.fixture
def vehiculo(db):
    return Vehiculo.objects.create(
        placa="ABC123",
        marca="FOTON",
        referencia="BJ1044",
        modelo=2025,
        km_actual=1000,
    )


@pytest.fixture(autouse=True)
def media_temporal(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def url_galeria(vehiculo):
    return reverse("flota:fotos", args=[vehiculo.placa])


def test_anonimo_va_al_login(client, url_galeria):
    respuesta = client.get(url_galeria)
    assert respuesta.status_code == 302
    assert reverse("login") in respuesta["Location"]


def test_el_conductor_no_puede_entrar(client, conductor, url_galeria):
    client.force_login(conductor)
    assert client.get(url_galeria).status_code == 403


def test_el_admin_ve_las_seis_ranuras(client, admin, url_galeria):
    client.force_login(admin)
    respuesta = client.get(url_galeria)
    contenido = respuesta.content.decode()
    assert respuesta.status_code == 200
    for etiqueta in (
        "Frontal",
        "Parte trasera",
        "Lateral izquierdo",
        "Lateral derecho",
        "Interior / cabina",
        "Tablero (kilometraje)",
    ):
        assert etiqueta in contenido
    assert contenido.count("Sin foto") == 6


def test_subir_una_foto_guarda_autor_y_redirige(client, admin, vehiculo, url_galeria):
    client.force_login(admin)
    imagen = SimpleUploadedFile("frontal.png", png_valido(), content_type="image/png")
    respuesta = client.post(
        url_galeria,
        {"tipo": FotoVehiculo.Tipo.FRONTAL, "imagen": imagen, "descripcion": "Paragolpes"},
        follow=True,
    )
    assert respuesta.status_code == 200
    foto = FotoVehiculo.objects.get()
    assert foto.vehiculo == vehiculo
    assert foto.tipo == FotoVehiculo.Tipo.FRONTAL
    assert foto.subido_por == admin
    assert foto.descripcion == "Paragolpes"
    assert "guardada" in respuesta.content.decode()


def test_cambiar_un_angulo_conserva_la_foto_anterior(client, admin, url_galeria):
    client.force_login(admin)
    for nombre in ("frontal1.png", "frontal2.png"):
        imagen = SimpleUploadedFile(nombre, png_valido(), content_type="image/png")
        client.post(
            url_galeria,
            {"tipo": FotoVehiculo.Tipo.FRONTAL, "imagen": imagen},
        )
    assert (
        FotoVehiculo.objects.filter(
            vehiculo__placa="ABC123", tipo=FotoVehiculo.Tipo.FRONTAL
        ).count()
        == 2
    )
    respuesta = client.get(url_galeria)
    assert "2 guardadas" in respuesta.content.decode()


def test_un_pdf_no_se_guarda_como_foto(client, admin, url_galeria):
    client.force_login(admin)
    falso = SimpleUploadedFile("documento.pdf", b"%PDF-1.4 no soy imagen")
    respuesta = client.post(
        url_galeria, {"tipo": FotoVehiculo.Tipo.FRONTAL, "imagen": falso}
    )
    assert respuesta.status_code == 200
    assert FotoVehiculo.objects.count() == 0
    assert "errorlist" in respuesta.content.decode()


def test_un_tipo_desconocido_no_crea_registros(client, admin, url_galeria):
    client.force_login(admin)
    imagen = SimpleUploadedFile("frontal.png", png_valido(), content_type="image/png")
    respuesta = client.post(url_galeria, {"tipo": "otro", "imagen": imagen})
    assert respuesta.status_code == 302
    assert FotoVehiculo.objects.count() == 0


def test_la_hoja_de_vida_enlaza_a_la_galeria(client, admin, vehiculo, url_galeria):
    client.force_login(admin)
    respuesta = client.get(reverse("flota:detalle", args=[vehiculo.placa]))
    assert respuesta.status_code == 200
    assert url_galeria in respuesta.content.decode()


def test_la_vista_360_enlaza_a_la_galeria(client, admin, vehiculo, url_galeria):
    client.force_login(admin)
    respuesta = client.get(reverse("hoja_vida_360", args=[vehiculo.placa]))
    assert respuesta.status_code == 200
    assert url_galeria in respuesta.content.decode()


def test_la_vista_360_cuenta_angulos_no_versiones(client, admin, vehiculo, url_galeria):
    """Dos fotos del mismo ángulo son una sola ranura ocupada, no dos."""
    client.force_login(admin)
    for nombre in ("frontal1.png", "frontal2.png"):
        imagen = SimpleUploadedFile(nombre, png_valido(), content_type="image/png")
        client.post(url_galeria, {"tipo": FotoVehiculo.Tipo.FRONTAL, "imagen": imagen})
    respuesta = client.get(reverse("hoja_vida_360", args=[vehiculo.placa]))
    assert "1 de 6 fotos de referencia" in respuesta.content.decode()
