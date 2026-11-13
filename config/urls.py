from django.contrib import admin
from django.urls import path

from config.views import inicio

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", inicio, name="inicio"),
]
