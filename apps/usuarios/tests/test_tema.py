import pytest
from django.urls import reverse

from apps.nucleo.errores import ReglaNegocio
from apps.usuarios import servicios
from apps.usuarios.models import Usuario


def test_cada_usuario_elige_su_tema(dueno, colaborador):
    servicios.cambiar_tema(colaborador, "oscuro")
    assert Usuario.objects.get(pk=colaborador.pk).tema == "oscuro"
    assert Usuario.objects.get(pk=dueno.pk).tema == "sistema"
    with pytest.raises(ReglaNegocio):
        servicios.cambiar_tema(colaborador, "rosado")


def test_boton_del_menu_cambia_el_tema(cliente_web, colaborador):
    web = cliente_web(colaborador)
    respuesta = web.post(reverse("usuarios:tema"), {"tema": "oscuro", "volver": "/inventario/"})
    assert respuesta.url == "/inventario/"
    pagina = web.get(reverse("inventario:lista")).content.decode()
    assert 'data-tema="oscuro"' in pagina
    assert "Modo claro" in pagina


def test_no_redirige_fuera_del_sitio(cliente_web, colaborador):
    respuesta = cliente_web(colaborador).post(
        reverse("usuarios:tema"), {"tema": "claro", "volver": "https://otro.sitio/"}
    )
    assert respuesta.url == reverse("inicio")
