from django.core.management import call_command
from django.urls import reverse

from apps.fiados.models import Cliente
from apps.inventario.servicios import verificar_existencias
from apps.usuarios.models import Usuario
from apps.ventas.models import Venta


def test_cargar_demo_crea_datos_coherentes_una_sola_vez(db):
    call_command("cargar_demo")
    call_command("cargar_demo")  # la segunda vez no hace nada
    assert Usuario.objects.count() == 3
    assert Venta.objects.count() == 5
    assert verificar_existencias() == []
    assert Cliente.objects.get(nombre="Cliente 1").saldo == 2 * 2_500 + 12 * 600
    hermano = Usuario.objects.get(usuario="hermano")
    assert hermano.tiene_permiso("vender")
    assert not hermano.tiene_permiso("inventario")


def test_entrada_muestra_usuarios_solo_en_modo_demo(client, settings, dueno):
    settings.DEMO = False
    assert "Versión de demostración" not in client.get(reverse("usuarios:login")).content.decode()
    settings.DEMO = True
    assert "Versión de demostración" in client.get(reverse("usuarios:login")).content.decode()
