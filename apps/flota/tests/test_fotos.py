"""Pruebas de las fotos del vehículo (capacidad de subir desde el PC)."""

from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from apps.flota.models import FotoVehiculo, Vehiculo


def png_valido(lado=1):
    """Genera un PNG real con Pillow: así la imagen sí pasa la validación."""
    buffer = BytesIO()
    Image.new("RGB", (lado, lado), "white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def imagen_png():
    return SimpleUploadedFile("frontal.png", png_valido(), content_type="image/png")


@pytest.fixture
def vehiculo(db):
    return Vehiculo.objects.create(
        placa="ABC123",
        marca="FOTON",
        referencia="BJ1044",
        modelo=2025,
        combustible=Vehiculo.Combustible.DIESEL,
        km_actual=1000,
    )


@pytest.fixture(autouse=True)
def media_temporal(settings, tmp_path):
    """Guarda las imágenes en una carpeta temporal para no ensuciar el proyecto."""
    settings.MEDIA_ROOT = tmp_path


def test_foto_se_guarda_con_nombre_descriptivo(vehiculo, imagen_png):
    foto = FotoVehiculo.objects.create(
        vehiculo=vehiculo, tipo=FotoVehiculo.Tipo.FRONTAL, imagen=imagen_png
    )
    hoy = timezone.localdate()
    assert foto.imagen.name == f"fotos/vehiculos/{hoy:%Y/%m}/ABC123-frontal.png"
    assert foto.nombre_archivo == "ABC123-frontal.png"


def test_un_vehiculo_puede_tener_varias_fotos(vehiculo, imagen_png):
    FotoVehiculo.objects.create(
        vehiculo=vehiculo, tipo=FotoVehiculo.Tipo.FRONTAL, imagen=imagen_png
    )
    segunda = SimpleUploadedFile("trasera.png", png_valido(), content_type="image/png")
    FotoVehiculo.objects.create(
        vehiculo=vehiculo, tipo=FotoVehiculo.Tipo.TRASERA, imagen=segunda
    )
    assert vehiculo.fotos.count() == 2


def test_el_mismo_angulo_puede_actualizarse_con_una_foto_nueva(vehiculo, imagen_png):
    """Se guarda una foto nueva del mismo ángulo sin borrar el historial."""
    FotoVehiculo.objects.create(
        vehiculo=vehiculo, tipo=FotoVehiculo.Tipo.FRONTAL, imagen=imagen_png
    )
    nueva = SimpleUploadedFile("frontal2.png", png_valido(), content_type="image/png")
    FotoVehiculo.objects.create(
        vehiculo=vehiculo, tipo=FotoVehiculo.Tipo.FRONTAL, imagen=nueva
    )
    assert vehiculo.fotos.filter(tipo=FotoVehiculo.Tipo.FRONTAL).count() == 2


def test_un_archivo_que_no_es_imagen_no_pasa_la_validacion(vehiculo):
    falso = SimpleUploadedFile("licencia.pdf", b"%PDF-1.4 no soy una imagen")
    foto = FotoVehiculo(vehiculo=vehiculo, tipo=FotoVehiculo.Tipo.FRONTAL, imagen=falso)
    with pytest.raises(ValidationError):
        foto.full_clean()


def test_una_imagen_de_mas_de_8_mb_se_rechaza(vehiculo, imagen_png):
    grande = SimpleUploadedFile("frontal.png", png_valido() + b"0" * (8 * 1024 * 1024))
    foto = FotoVehiculo(vehiculo=vehiculo, tipo=FotoVehiculo.Tipo.FRONTAL, imagen=grande)
    with pytest.raises(ValidationError) as error:
        foto.full_clean()
    assert "8 MB" in str(error.value)


def test_cada_foto_tiene_su_tipo_visible(vehiculo, imagen_png):
    foto = FotoVehiculo.objects.create(
        vehiculo=vehiculo,
        tipo=FotoVehiculo.Tipo.LATERAL_DERECHO,
        imagen=imagen_png,
        descripcion="Costado derecho, sin rayones",
    )
    assert str(foto) == "ABC123 · Lateral derecho"
    assert foto.descripcion == "Costado derecho, sin rayones"


def test_las_fotos_se_ordenan_por_placa_y_tipo(vehiculo, imagen_png):
    otro = Vehiculo.objects.create(
        placa="XYZ789", marca="CHEVROLET", referencia="NHR", modelo=2018, km_actual=20000
    )
    for auto in (otro, vehiculo):
        FotoVehiculo.objects.create(
            vehiculo=auto, tipo=FotoVehiculo.Tipo.FRONTAL, imagen=imagen_png
        )
    assert [f.vehiculo.placa for f in FotoVehiculo.objects.all()] == ["ABC123", "XYZ789"]


def test_el_vencimiento_del_documento_sigue_siendo_obligatorio(vehiculo):
    """El soporte ya es opcional (R19), pero la fecha de vencimiento no."""
    from apps.flota.models import Documento

    documento = Documento(tipo=Documento.Tipo.SOAT, vehiculo=vehiculo)
    with pytest.raises(ValidationError) as error:
        documento.full_clean()

    assert "vencimiento" in error.value.message_dict
