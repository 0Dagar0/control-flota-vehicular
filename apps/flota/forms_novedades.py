"""Formularios de novedades (v0.7, contrato §5.1 y §5.2)."""

from django import forms

from .models import Novedad


class NovedadReportarForm(forms.ModelForm):
    """Reporte del conductor: descripción y severidad (las fotos van aparte)."""

    class Meta:
        model = Novedad
        fields = ("descripcion", "severidad")
        labels = {
            "descripcion": "descripción",
            "severidad": "severidad",
        }
        widgets = {
            "descripcion": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Qué pasó, dónde y cómo lo notaste"}
            ),
        }

    def clean_descripcion(self):
        valor = self.cleaned_data["descripcion"].strip()
        if len(valor) < 10:
            raise forms.ValidationError("Describe la novedad con al menos 10 caracteres.")
        return valor


class NovedadGestionForm(forms.Form):
    """Cambio de estado del administrador, limitado a las transiciones válidas."""

    estado = forms.ChoiceField(label="nuevo estado", choices=())
    descripcion = forms.CharField(
        label="descripción de la gestión",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, transiciones=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estado"].choices = [
            (estado, Novedad.Estado(estado).label) for estado in transiciones
        ]
