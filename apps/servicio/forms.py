"""Formularios del servicio del conductor (v0.5).

El conductor no elige vehículo: lo toma de la asignación que hizo el
administrador. Por eso los formularios reciben la asignación o el servicio ya
resuelto por la vista y solo validan los datos que dependen de él.
"""

from django import forms
from django.utils import timezone

from apps.flota.models import Servicio


class ServicioIniciarForm(forms.Form):
    """Inicio del recorrido: kilometraje y ruta (contrato §5.1)."""

    km_inicial = forms.IntegerField(label="kilometraje inicial", min_value=0)
    ruta = forms.CharField(
        label="ruta u operación",
        max_length=200,
        min_length=5,
        widget=forms.TextInput(
            attrs={"placeholder": "Por ejemplo: Ruta norte, bodega → Soacha"}
        ),
        help_text="Describe el recorrido que vas a hacer hoy.",
    )

    def __init__(self, *args, asignacion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.asignacion = asignacion
        if asignacion:
            self.fields["km_inicial"].initial = asignacion.vehiculo.km_actual
            self.fields["km_inicial"].help_text = (
                f"El vehículo {asignacion.vehiculo.placa} tiene "
                f"{asignacion.vehiculo.km_actual} km. No puede ser menor (R12)."
            )

    def clean_km_inicial(self):
        km = self.cleaned_data["km_inicial"]
        if self.asignacion and km < self.asignacion.vehiculo.km_actual:
            raise forms.ValidationError(
                "El kilometraje no puede ser menor al último registrado "
                f"({self.asignacion.vehiculo.km_actual} km)."
            )
        return km


class ServicioCerrarForm(forms.Form):
    """Cierre del recorrido. Se puede cerrar **sin novedad**."""

    km_final = forms.IntegerField(label="kilometraje final", min_value=0)
    sin_novedad = forms.BooleanField(
        label="Cerrar sin novedad",
        required=False,
        initial=True,
        help_text="Si hubo un problema, desmarca esta casilla y descríbelo.",
    )
    observacion_cierre = forms.CharField(
        label="observación del cierre",
        max_length=200,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Qué pasó durante el recorrido (llantas, luces, tráfico, carga...).",
    )

    def __init__(self, *args, servicio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.servicio = servicio
        if servicio:
            self.fields["km_final"].initial = servicio.km_inicial

    def clean_km_final(self):
        km = self.cleaned_data["km_final"]
        if self.servicio and km < self.servicio.km_inicial:
            raise forms.ValidationError(
                f"El kilometraje final no puede ser menor al inicial "
                f"({self.servicio.km_inicial} km)."
            )
        return km

    def clean(self):
        datos = super().clean()
        if not datos.get("sin_novedad") and not datos.get("observacion_cierre"):
            self.add_error(
                "observacion_cierre",
                "Si no cierras sin novedad, describe qué pasó.",
            )
        return datos

    def crear_cierre(self, servicio: Servicio) -> Servicio:
        """Aplica el cierre al servicio (el modelo valida la regla R12)."""
        datos = self.cleaned_data
        servicio.km_final = datos["km_final"]
        servicio.sin_novedad = datos["sin_novedad"]
        servicio.observacion_cierre = datos["observacion_cierre"]
        servicio.cerrado_en = servicio.cerrado_en or timezone.now()
        servicio.full_clean()
        servicio.save()
        return servicio
