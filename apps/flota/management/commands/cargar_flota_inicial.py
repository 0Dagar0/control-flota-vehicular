"""Carga los vehículos y documentos de la flota inicial desde un archivo JSON.

Se puede ejecutar varias veces: si la placa ya existe, actualiza los datos en
lugar de duplicar el vehículo, y lo mismo con cada documento (se identifica por
vehículo + tipo). Respeta la regla R12 (el kilometraje no baja): si el JSON trae
un kilometraje menor que el guardado, se detiene sin cambiar nada.

Los documentos se crean con el soporte pendiente (R19): las fotos o PDF se
suben después desde el PC.

Uso (desde la carpeta ``App``)::

    .venv\\Scripts\\python.exe manage.py cargar_flota_inicial
    .venv\\Scripts\\python.exe manage.py cargar_flota_inicial --archivo datos/ejemplo.json
"""

import json
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.flota.models import Documento, Vehiculo

ARCHIVO_POR_DEFECTO = "datos/flota_inicial.json"


class Command(BaseCommand):
    help = "Crea o actualiza los vehículos y documentos de la flota inicial (no duplica)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--archivo",
            default=ARCHIVO_POR_DEFECTO,
            help=f"Ruta del JSON con los datos (por defecto {ARCHIVO_POR_DEFECTO}).",
        )

    def handle(self, *args, **opciones):
        ruta = Path(opciones["archivo"])
        if not ruta.is_absolute():
            ruta = Path(settings.BASE_DIR) / ruta
        if not ruta.exists():
            raise CommandError(f"No se encontró el archivo: {ruta}")

        datos = json.loads(ruta.read_text(encoding="utf-8"))
        vehiculos = datos.get("vehiculos", [])
        documentos = datos.get("documentos", [])
        if not vehiculos:
            raise CommandError("El archivo no contiene vehículos.")

        with transaction.atomic():
            creados, actualizados = self._cargar_vehiculos(vehiculos)
            docs_creados, docs_actualizados = self._cargar_documentos(documentos)

        self.stdout.write(
            self.style.SUCCESS(
                f"Listo. Vehículos: {creados} creados, {actualizados} actualizados. "
                f"Documentos: {docs_creados} creados, {docs_actualizados} actualizados."
            )
        )

    def _cargar_vehiculos(self, vehiculos):
        creados = actualizados = 0
        for dato in vehiculos:
            placa = str(dato["placa"]).strip().upper()
            campos = {
                "marca": dato["marca"],
                "referencia": dato["referencia"],
                "modelo": dato["modelo"],
                "tipo_carroceria": dato.get("tipo_carroceria", ""),
                "vin": dato.get("vin", ""),
                "motor": dato.get("motor", ""),
                "combustible": dato.get("combustible", Vehiculo.Combustible.GASOLINA),
                "km_actual": dato.get("km_actual", 0),
                "propietario": dato.get("propietario", ""),
            }

            existente = Vehiculo.objects.filter(placa=placa).first()
            vehiculo = existente or Vehiculo(placa=placa)
            for campo, valor in campos.items():
                setattr(vehiculo, campo, valor)

            try:
                vehiculo.full_clean()
            except ValidationError as error:
                raise CommandError(f"{placa}: {error.message_dict}") from error

            vehiculo.save()
            if existente:
                actualizados += 1
                self.stdout.write(f"Vehículo actualizado: {vehiculo}")
            else:
                creados += 1
                self.stdout.write(f"Vehículo creado: {vehiculo}")
        return creados, actualizados

    def _cargar_documentos(self, documentos):
        creados = actualizados = 0
        tipos_validos = {valor for valor, _ in Documento.Tipo.choices}
        for dato in documentos:
            placa = str(dato["placa"]).strip().upper()
            tipo = dato["tipo"]
            if tipo not in tipos_validos:
                raise CommandError(f"{placa}: tipo de documento desconocido '{tipo}'.")

            vehiculo = Vehiculo.objects.filter(placa=placa).first()
            if vehiculo is None:
                raise CommandError(f"{placa}: el vehículo del documento no existe.")

            existente = Documento.objects.filter(vehiculo=vehiculo, tipo=tipo).first()
            documento = existente or Documento(vehiculo=vehiculo, tipo=tipo)
            documento.entidad = dato.get("entidad", "")
            documento.numero = dato.get("numero", "")
            documento.vencimiento = date.fromisoformat(dato["vencimiento"])

            try:
                documento.full_clean()
            except ValidationError as error:
                raise CommandError(f"{placa} · {tipo}: {error.message_dict}") from error

            documento.save()
            if existente:
                actualizados += 1
            else:
                creados += 1
                self.stdout.write(f"Documento creado: {documento} (soporte pendiente)")
        return creados, actualizados
