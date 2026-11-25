"""Formularios de las preferencias de notificaciones."""

from django import forms

from .models import PreferenciaNotificacion


class PreferenciaForm(forms.ModelForm):
    """Canales opcionales; la app y los críticos nunca aparecen como opción."""

    class Meta:
        model = PreferenciaNotificacion
        fields = ("correo", "telegram", "web_push", "resumen_diario", "hora_resumen")
        widgets = {
            "hora_resumen": forms.TimeInput(attrs={"type": "time"}),
        }
        labels = {
            "correo": "Recibir avisos por correo",
            "telegram": "Recibir urgencias por Telegram",
            "web_push": "Recibir urgencias en el navegador (Web Push)",
            "resumen_diario": "Recibir el resumen diario",
            "hora_resumen": "Hora del resumen diario",
        }
        help_texts = {
            "telegram": "Necesitas abrir el bot y guardar tu chat_id en tu usuario.",
            "web_push": (
                "Activa los avisos en este navegador desde la pantalla de preferencias."
            ),
        }
