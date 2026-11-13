from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("documento", "first_name", "last_name", "email", "rol", "is_active")
    list_filter = ("rol", "is_active", "is_staff")
    search_fields = ("documento", "first_name", "last_name", "email")
    ordering = ("documento",)

    fieldsets = (
        (None, {"fields": ("documento", "password")}),
        ("Datos personales", {"fields": ("first_name", "last_name", "email", "telefono")}),
        (
            "Rol y acceso",
            {
                "fields": (
                    "rol",
                    "telegram_chat_id",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "documento",
                    "first_name",
                    "last_name",
                    "email",
                    "telefono",
                    "rol",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
