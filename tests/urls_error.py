"""URLconf de prueba: una vista que falla para comprobar la plantilla 500."""

from django.urls import path


def explotar(request):
    raise RuntimeError("Fallo provocado por la prueba")


urlpatterns = [path("boom/", explotar, name="boom")]
