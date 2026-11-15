import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.mark.django_db
def test_pagina_estado_responde(client):
    respuesta = client.get(reverse("estado"))

    assert respuesta.status_code == 200
    assert "Mi Flota" in respuesta.content.decode()


@pytest.mark.django_db
def test_usuario_nuevo_es_conductor_por_defecto():
    Usuario = get_user_model()

    usuario = Usuario.objects.create_user(
        documento="12345678",
        email="conductor@ejemplo.com",
        password="ClaveSegura2026",
        first_name="Andrés",
        last_name="Pérez",
    )

    assert usuario.rol == Usuario.Rol.CONDUCTOR
    assert usuario.es_conductor is True
    assert usuario.es_admin is False
    assert "12345678" in str(usuario)
