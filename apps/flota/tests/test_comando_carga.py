"""Pruebas del comando que carga la flota inicial desde JSON."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.flota.models import Documento, Vehiculo

EJEMPLO = "datos/flota_inicial.ejemplo.json"


@pytest.mark.django_db
def test_carga_vehiculos_y_documentos_del_ejemplo():
    call_command("cargar_flota_inicial", "--archivo", EJEMPLO, stdout=StringIO())

    assert Vehiculo.objects.count() == 2
    assert Documento.objects.count() == 3
    assert Vehiculo.objects.get(placa="ABC123").km_actual == 15000


@pytest.mark.django_db
def test_los_documentos_quedan_con_soporte_pendiente():
    call_command("cargar_flota_inicial", "--archivo", EJEMPLO, stdout=StringIO())

    soat = Documento.objects.get(vehiculo__placa="ABC123", tipo=Documento.Tipo.SOAT)
    assert soat.tiene_soporte is False
    assert soat.estado_soporte == "Pendiente"
    assert soat.vencimiento.isoformat() == "2027-06-30"


@pytest.mark.django_db
def test_ejecutarlo_dos_veces_no_duplica_nada():
    salida = StringIO()
    call_command("cargar_flota_inicial", "--archivo", EJEMPLO, stdout=salida)
    call_command("cargar_flota_inicial", "--archivo", EJEMPLO, stdout=salida)

    assert Vehiculo.objects.count() == 2
    assert Documento.objects.count() == 3
    assert "0 creados, 2 actualizados" in salida.getvalue()
    assert "0 creados, 3 actualizados" in salida.getvalue()


@pytest.mark.django_db
def test_no_permite_bajar_el_kilometraje(tmp_path):
    """R12: si el JSON trae menos kilómetros que los guardados, se detiene."""
    archivo = tmp_path / "flota.json"
    archivo.write_text(
        """
        {
          "vehiculos": [
            {"placa": "AAA111", "marca": "FOTON", "referencia": "X", "modelo": 2020,
             "km_actual": 50000}
          ]
        }
        """,
        encoding="utf-8",
    )
    call_command("cargar_flota_inicial", "--archivo", str(archivo), stdout=StringIO())

    archivo.write_text(
        """
        {
          "vehiculos": [
            {"placa": "AAA111", "marca": "FOTON", "referencia": "X", "modelo": 2020,
             "km_actual": 49000}
          ]
        }
        """,
        encoding="utf-8",
    )
    with pytest.raises(CommandError) as error:
        call_command("cargar_flota_inicial", "--archivo", str(archivo), stdout=StringIO())

    assert "kilometraje" in str(error.value).lower()
    assert Vehiculo.objects.get(placa="AAA111").km_actual == 50000


@pytest.mark.django_db
def test_avisa_si_el_vehiculo_del_documento_no_existe(tmp_path):
    archivo = tmp_path / "flota.json"
    archivo.write_text(
        """
        {
          "vehiculos": [],
          "documentos": [{"placa": "ZZZ999", "tipo": "soat", "vencimiento": "2027-01-01"}]
        }
        """,
        encoding="utf-8",
    )
    with pytest.raises(CommandError):
        call_command("cargar_flota_inicial", "--archivo", str(archivo), stdout=StringIO())
