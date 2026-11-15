"""Administración de la flota en el panel de Django."""

from django.contrib import admin

from .models import Conductor, Configuracion, Documento, FotoVehiculo, Vehiculo


class DocumentoVehiculoInline(admin.TabularInline):
    """Documentos del vehículo dentro de la ficha del vehículo."""

    model = Documento
    fk_name = "vehiculo"
    extra = 0
    fields = ("tipo", "entidad", "numero", "vencimiento", "soporte")
    verbose_name = "documento del vehículo"
    verbose_name_plural = "documentos del vehículo"


class FotoVehiculoInline(admin.TabularInline):
    """Fotos de la hoja de vida dentro de la ficha del vehículo."""

    model = FotoVehiculo
    extra = 0
    fields = ("tipo", "imagen", "descripcion", "subida_en")
    readonly_fields = ("subida_en",)
    verbose_name = "foto del vehículo"
    verbose_name_plural = "fotos del vehículo"


class DocumentoConductorInline(admin.TabularInline):
    """Documentos del conductor dentro de la ficha del conductor."""

    model = Documento
    fk_name = "conductor"
    extra = 0
    fields = ("tipo", "entidad", "numero", "vencimiento", "soporte")
    verbose_name = "documento del conductor"
    verbose_name_plural = "documentos del conductor"


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ("placa", "marca", "referencia", "modelo", "km_actual", "estado", "activo")
    list_filter = ("activo", "combustible", "marca")
    search_fields = ("placa", "vin", "marca", "referencia")
    ordering = ("placa",)
    readonly_fields = ("creado_en", "creado_por", "actualizado_en", "estado")
    inlines = (DocumentoVehiculoInline, FotoVehiculoInline)
    fieldsets = (
        (None, {"fields": ("placa", "marca", "referencia", "modelo", "tipo_carroceria")}),
        ("Identificación", {"fields": ("vin", "motor", "combustible", "propietario")}),
        ("Operación", {"fields": ("km_actual", "activo", "estado")}),
        ("Auditoría", {"fields": ("creado_en", "creado_por", "actualizado_en")}),
    )

    @admin.display(description="estado", ordering="activo")
    def estado(self, obj):
        return obj.Estado(obj.estado).label

    def save_model(self, request, obj, form, change):
        if not obj.creado_por_id:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(Conductor)
class ConductorAdmin(admin.ModelAdmin):
    list_display = (
        "usuario",
        "licencia_categoria",
        "licencia_vencimiento",
        "estado",
        "activo",
        "fecha_baja",
    )
    list_filter = ("activo", "licencia_categoria")
    search_fields = ("usuario__documento", "usuario__first_name", "usuario__last_name")
    autocomplete_fields = ("usuario",)
    readonly_fields = ("creado_en", "creado_por", "actualizado_en", "estado")
    inlines = (DocumentoConductorInline,)
    fieldsets = (
        ("Conductor", {"fields": ("usuario", "licencia_categoria", "licencia_vencimiento")}),
        (
            "Contacto de emergencia",
            {"fields": ("contacto_emergencia_nombre", "contacto_emergencia_telefono")},
        ),
        ("Estado", {"fields": ("activo", "fecha_baja", "motivo_baja", "estado")}),
        ("Auditoría", {"fields": ("creado_en", "creado_por", "actualizado_en")}),
    )

    @admin.display(description="estado", ordering="activo")
    def estado(self, obj):
        return obj.Estado(obj.estado).label

    def save_model(self, request, obj, form, change):
        if not obj.creado_por_id:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)


class FiltroSoporte(admin.SimpleListFilter):
    """Permite separar los documentos que ya tienen foto de los que no."""

    title = "soporte"
    parameter_name = "soporte"

    def lookups(self, request, model_admin):
        return (("cargado", "Con soporte"), ("pendiente", "Soporte pendiente"))

    def queryset(self, request, queryset):
        if self.value() == "cargado":
            return queryset.exclude(soporte="")
        if self.value() == "pendiente":
            return queryset.filter(soporte="")
        return queryset


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = (
        "tipo",
        "vehiculo",
        "conductor",
        "vencimiento",
        "estado",
        "estado_soporte",
        "soporte",
    )
    list_filter = ("tipo", FiltroSoporte, "vencimiento")
    search_fields = ("vehiculo__placa", "conductor__usuario__documento", "numero", "entidad")
    autocomplete_fields = ("vehiculo", "conductor")
    date_hierarchy = "vencimiento"
    readonly_fields = ("creado_en", "creado_por", "actualizado_en", "estado", "estado_soporte")

    @admin.display(description="vencimiento")
    def estado(self, obj):
        return obj.estado

    @admin.display(description="soporte", ordering="soporte")
    def estado_soporte(self, obj):
        return obj.estado_soporte

    def save_model(self, request, obj, form, change):
        if not obj.creado_por_id:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(FotoVehiculo)
class FotoVehiculoAdmin(admin.ModelAdmin):
    """Bandeja de fotos: permite buscar, filtrar y subir desde el equipo."""

    list_display = ("vehiculo", "tipo", "descripcion", "subida_en", "subido_por")
    list_filter = ("tipo", "vehiculo__marca")
    search_fields = ("vehiculo__placa", "descripcion")
    autocomplete_fields = ("vehiculo",)
    readonly_fields = ("subida_en", "subido_por")

    def save_model(self, request, obj, form, change):
        if not obj.subido_por_id:
            obj.subido_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(Configuracion)
class ConfiguracionAdmin(admin.ModelAdmin):
    list_display = (
        "umbral_mantenimiento_km",
        "minutos_autorizacion",
        "dias_aviso_documento",
        "actualizado_en",
    )

    def has_add_permission(self, request):
        # Solo puede existir un registro de configuración.
        return not Configuracion.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
