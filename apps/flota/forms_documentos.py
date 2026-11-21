"""Formulario de renovación de documentos (v0.9)."""

from django import forms
from django.utils import timezone

from .models import Documento


class DocumentoRenovarForm(forms.ModelForm):
    """Renueva un documento existente: nueva fecha, datos y soporte opcional."""

    class Meta:
        model = Documento
        fields = ("entidad", "numero", "vencimiento", "soporte")
        labels = {
            "entidad": "entidad o aseguradora",
            "numero": "número",
            "vencimiento": "nuevo vencimiento",
            "soporte": "soporte (foto o PDF)",
        }
        widgets = {"vencimiento": forms.DateInput(attrs={"type": "date"})}

    def clean_vencimiento(self):
        valor = self.cleaned_data["vencimiento"]
        if valor <= timezone.localdate():
            raise forms.ValidationError("El nuevo vencimiento debe ser una fecha futura.")
        return valor
