from datetime import timedelta

import pytest
from django.urls import reverse

from apps.inventario.models import MovimientoInventario, TipoMovimiento
from apps.nucleo.errores import ReglaNegocio
from apps.nucleo.fechas import hoy
from apps.pedidos import servicios
from apps.pedidos.models import EstadoPedido, Pedido


@pytest.fixture
def proveedor(dueno):
    return servicios.crear_proveedor(dueno, "Proveedor A", "300 000 0000")


def _pedir(usuario, producto, proveedor, cantidad=10_000, costo=4_500, fecha=None):
    return servicios.crear_pedido(
        usuario,
        producto_id=producto.pk,
        proveedor_id=proveedor.pk,
        cantidad=cantidad,
        costo_unitario=costo,
        fecha_pedido=fecha,
    )


def test_crear_pedido_no_toca_el_inventario(colaborador, tomate, proveedor):
    pedido = _pedir(colaborador, tomate, proveedor)
    assert pedido.estado == EstadoPedido.PENDIENTE
    assert pedido.creado_por == colaborador
    tomate.refresh_from_db()
    assert tomate.existencia == 10_000


def test_aviso_de_pedido_repetido(colaborador, tomate, atun, proveedor):
    _pedir(colaborador, tomate, proveedor)
    assert servicios.pendientes_de(tomate.pk).count() == 1
    assert servicios.pendientes_de(atun.pk).count() == 0


def test_recibir_suma_lo_que_llego_y_calcula_el_gasto(colaborador, tomate, proveedor):
    pedido = _pedir(colaborador, tomate, proveedor, cantidad=10_000, costo=4_500)
    recibido = servicios.recibir_pedido(
        colaborador, pedido_id=pedido.pk, cantidad_recibida=8_000, costo_unitario=4_500
    )
    tomate.refresh_from_db()
    assert recibido.estado == EstadoPedido.RECIBIDO
    assert recibido.gasto == 36_000  # 8 kg × $4.500
    assert recibido.faltante == 2_000
    assert tomate.existencia == 18_000
    movimiento = MovimientoInventario.objects.get(origen=f"pedido:{pedido.pk}")
    assert movimiento.tipo == TipoMovimiento.RECEPCION


def test_un_pedido_se_recibe_una_sola_vez(colaborador, tomate, proveedor):
    pedido = _pedir(colaborador, tomate, proveedor)
    servicios.recibir_pedido(
        colaborador, pedido_id=pedido.pk, cantidad_recibida=1, costo_unitario=1
    )
    with pytest.raises(ReglaNegocio, match="ya fue recibido"):
        servicios.recibir_pedido(
            colaborador, pedido_id=pedido.pk, cantidad_recibida=1, costo_unitario=1
        )
    assert MovimientoInventario.objects.filter(origen=f"pedido:{pedido.pk}").count() == 1


def test_cancelar_no_suma_y_no_se_puede_recibir(colaborador, tomate, proveedor):
    pedido = _pedir(colaborador, tomate, proveedor)
    servicios.cancelar_pedido(colaborador, pedido_id=pedido.pk)
    assert Pedido.objects.get(pk=pedido.pk).estado == EstadoPedido.CANCELADO
    assert servicios.pendientes_de(tomate.pk).count() == 0
    with pytest.raises(ReglaNegocio):
        servicios.recibir_pedido(
            colaborador, pedido_id=pedido.pk, cantidad_recibida=1, costo_unitario=1
        )


def test_fechas_validas(colaborador, tomate, proveedor):
    with pytest.raises(ReglaNegocio, match="futura"):
        _pedir(colaborador, tomate, proveedor, fecha=hoy() + timedelta(days=1))
    pedido = _pedir(colaborador, tomate, proveedor, fecha=hoy() - timedelta(days=3))
    with pytest.raises(ReglaNegocio, match="fecha de llegada"):
        servicios.recibir_pedido(
            colaborador,
            pedido_id=pedido.pk,
            cantidad_recibida=1,
            costo_unitario=1,
            fecha_llegada=hoy() - timedelta(days=5),
        )


def test_permisos(crear_colaborador, tomate, proveedor):
    solo_vende = crear_colaborador(permisos={"vender"})
    with pytest.raises(ReglaNegocio):
        _pedir(solo_vende, tomate, proveedor)
    with pytest.raises(ReglaNegocio):
        servicios.crear_proveedor(solo_vende, "Otro")


def test_proveedor_con_mismo_nombre(dueno, proveedor):
    assert servicios.proveedores_con_mismo_nombre("  proveedor a ") == [proveedor]


# --- Pantallas --------------------------------------------------------------


def test_flujo_de_pantallas(cliente_web, colaborador, tomate, proveedor):
    web = cliente_web(colaborador)
    respuesta = web.post(
        reverse("pedidos:nuevo"),
        {
            "producto_id": tomate.pk,
            "cantidad": "10",
            "costo_unitario": "4.500",
            "proveedor_id": proveedor.pk,
            "fecha_pedido": hoy().isoformat(),
        },
    )
    assert respuesta.status_code == 302
    pedido = Pedido.objects.get()
    assert pedido.cantidad == 10_000

    pagina = web.get(reverse("pedidos:elegir_producto", args=[tomate.pk])).content.decode()
    assert "Ya pediste este producto" in pagina

    # "Actualizar resumen" no confirma la llegada.
    web.post(
        reverse("pedidos:recibir", args=[pedido.pk]),
        {
            "cantidad_recibida": "8",
            "costo_unitario": "4.500",
            "fecha_llegada": hoy().isoformat(),
            "revisar": "1",
        },
    )
    assert Pedido.objects.get().estado == EstadoPedido.PENDIENTE

    web.post(
        reverse("pedidos:recibir", args=[pedido.pk]),
        {"cantidad_recibida": "8", "costo_unitario": "4.500", "fecha_llegada": hoy().isoformat()},
    )
    assert Pedido.objects.get().gasto == 36_000
    assert "Pedido pendiente" not in web.get(reverse("inventario:lista")).content.decode()


def test_inventario_muestra_pedido_pendiente(cliente_web, colaborador, tomate, proveedor):
    _pedir(colaborador, tomate, proveedor)
    pagina = cliente_web(colaborador).get(reverse("inventario:lista")).content.decode()
    assert "Pedido pendiente" in pagina


def test_fechas_se_muestran_en_formato_del_navegador(cliente_web, colaborador, tomate, proveedor):
    """type=date necesita AAAA-MM-DD; con el formato local el campo quedaría vacío."""
    pedido = _pedir(colaborador, tomate, proveedor)
    web = cliente_web(colaborador)
    assert f'value="{hoy().isoformat()}"' in web.get(reverse("pedidos:nuevo")).content.decode()
    pagina = web.get(reverse("pedidos:recibir", args=[pedido.pk])).content.decode()
    assert f'value="{hoy().isoformat()}"' in pagina
