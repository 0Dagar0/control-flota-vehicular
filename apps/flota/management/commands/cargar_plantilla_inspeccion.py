"""Carga la plantilla «Rápida» con los 7 ítems aprobados por el dueño el 18/11/2026.

Se puede ejecutar varias veces: si la plantilla o un ítem ya existen, actualiza
sus datos en lugar de duplicarlos. Los nombres y grupos salen de
``Avances/maquetas/LEEME-inspeccion-rapida.md``.

Uso (desde la carpeta ``App``)::

    .venv\\Scripts\\python.exe manage.py cargar_plantilla_inspeccion
"""

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.flota.models import ItemInspeccion, PlantillaInspeccion

NOMBRE_PLANTILLA = "Rápida"

# (grupo, nombre, es_critico, requiere_foto) en el orden aprobado.
ITEMS = (
    ("Luces y visibilidad", "Luces delanteras", True, True),
    ("Luces y visibilidad", "Luces traseras", True, True),
    ("Motor y fluidos", "Nivel de aceite", True, True),
    ("Frenos y llantas", "Frenos", True, True),
    ("Frenos y llantas", "Llantas", True, True),
    ("Seguridad a bordo", "Kit de carretera", False, False),
    ("Seguridad a bordo", "Botiquín", False, False),
)


class Command(BaseCommand):
    help = "Crea o actualiza la plantilla «Rápida» y sus 7 ítems (no duplica)."

    @transaction.atomic
    def handle(self, *args, **opciones):
        plantilla, creada = PlantillaInspeccion.objects.update_or_create(
            nombre=NOMBRE_PLANTILLA,
            defaults={
                "nivel": PlantillaInspeccion.Nivel.RAPIDA,
                "activa": True,
            },
        )
        try:
            plantilla.full_clean()
        except ValidationError as error:
            raise CommandError(f"Plantilla inválida: {error.message_dict}") from error

        nuevos = 0
        actualizados = 0
        for orden, (grupo, nombre, critico, requiere_foto) in enumerate(ITEMS, start=1):
            item, item_creado = ItemInspeccion.objects.update_or_create(
                plantilla=plantilla,
                nombre=nombre,
                defaults={
                    "grupo": grupo,
                    "es_critico": critico,
                    "requiere_foto": requiere_foto,
                    "orden": orden,
                },
            )
            try:
                item.full_clean()
            except ValidationError as error:
                raise CommandError(f"Ítem '{nombre}': {error.message_dict}") from error
            if item_creado:
                nuevos += 1
            else:
                actualizados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Plantilla '{plantilla}' ({'creada' if creada else 'actualizada'}): "
                f"{nuevos} ítems nuevos, {actualizados} actualizados. Total {len(ITEMS)}."
            )
        )
