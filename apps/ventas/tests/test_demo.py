from django.core.management import call_command
from django.db.models import Sum
from django.urls import reverse

from apps.catalogo.models import Producto
from apps.fiados.models import Cliente
from apps.inventario.servicios import verificar_existencias
from apps.pedidos.models import EstadoPedido, Pedido
from apps.reportes import servicios as servicios_reportes
from apps.usuarios.models import Usuario
from apps.ventas.models import Venta


def test_cargar_demo_crea_datos_coherentes_una_sola_vez(db):
    call_command("cargar_demo")
    total_ventas = Venta.objects.count()
    call_command("cargar_demo")  # la segunda vez no carga nada
    assert Venta.objects.count() == total_ventas > 100
    assert Usuario.objects.count() == 3
    assert verificar_existencias() == []
    assert not Producto.objects.filter(existencia__lt=0).exists()
    assert Pedido.objects.filter(estado=EstadoPedido.PENDIENTE).count() == 4
    assert servicios_reportes.estadisticas(30).cantidad > 100
    for c in Cliente.objects.all():
        suma = c.movimientos.aggregate(s=Sum("monto"))["s"] or 0
        assert c.saldo == suma >= 0
    hermano = Usuario.objects.get(usuario="hermano")
    assert hermano.tiene_permiso("vender")
    assert not hermano.tiene_permiso("inventario")


def test_entrada_muestra_usuarios_solo_en_modo_demo(client, settings, dueno):
    settings.DEMO = False
    assert "Versión de demostración" not in client.get(reverse("usuarios:login")).content.decode()
    settings.DEMO = True
    assert "Versión de demostración" in client.get(reverse("usuarios:login")).content.decode()
