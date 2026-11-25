"""Formulario para subir o reemplazar una foto del vehículo.

La foto se guarda como un registro nuevo: reemplazar un ángulo no borra la
anterior (historial). El tipo llega como campo oculto desde la galería y la
vista comprueba que sea una de las seis opciones del modelo.
"""

from django import forms

from .models import FotoVehiculo


class FotoVehiculoForm(forms.ModelForm):
    """Sube una foto; el vehículo y el tipo los pone la vista."""

    class Meta:
        model = FotoVehiculo
        fields = ("imagen", "descripcion")
        labels = {
            "imagen": "archivo (JPG, PNG o WEBP, máximo 8 MB)",
            "descripcion": "descripción (opcional)",
        }
        widgets = {
            "descripcion": forms.TextInput(
                attrs={"placeholder": "Ej.: costado derecho sin rayones"}
            ),
        }
