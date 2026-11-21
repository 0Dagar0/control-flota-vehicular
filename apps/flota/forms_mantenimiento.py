"""Formularios de mantenimientos e incidentes (v1.1, contrato §5.4)."""

from django import forms
from django.utils import timezone

from .models import Incidente, Mantenimiento


class MantenimientoForm(forms.ModelForm):
    """Registro manual: el sistema no deduce intervalos por marca (R16/R17)."""

    class Meta:
        model = Mantenimiento
        fields = (
            "vehiculo",
            "tipo",
            "servicio",
            "parte",
            "fecha",
            "km",
            "proximo_km",
            "proxima_fecha",
            "costo",
            "observaciones",
            "soporte_factura",
        )
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "proxima_fecha": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        datos = super().clean()
        vehiculo = datos.get("vehiculo")
        km = datos.get("km")
        proximo_km = datos.get("proximo_km")
        fecha = datos.get("fecha")

        if fecha and fecha > timezone.localdate():
            self.add_error("fecha", "La fecha no puede ser futura (R17).")
        if km is not None and proximo_km is not None and proximo_km <= km:
            self.add_error(
                "proximo_km", "El próximo km debe ser mayor al km actual (R16)."
            )
        if vehiculo and km is not None and km < vehiculo.km_actual:
            self.add_error(
                "km", f"El km no puede ser menor al último registrado ({vehiculo.km_actual})."
            )
        return datos


class IncidenteForm(forms.ModelForm):
    class Meta:
        model = Incidente
        fields = (
            "vehiculo",
            "conductor",
            "fecha",
            "gravedad",
            "descripcion",
            "causa",
            "accion",
        )
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "causa": forms.Textarea(attrs={"rows": 3}),
            "accion": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_fecha(self):
        valor = self.cleaned_data["fecha"]
        if valor > timezone.localdate():
            raise forms.ValidationError("La fecha no puede ser futura (R17).")
        return valor
