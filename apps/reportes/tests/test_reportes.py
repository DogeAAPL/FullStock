import uuid

import pytest
from django.urls import reverse

from apps.fiados import servicios as fiados
from apps.inventario.servicios import corregir_existencia
from apps.nucleo.errores import ReglaNegocio
from apps.nucleo.fechas import hoy
from apps.pedidos import servicios as pedidos
from apps.reportes import servicios
from apps.ventas import servicios as ventas
from apps.ventas.servicios import LineaNueva


@pytest.fixture
def dia_con_movimiento(dueno, colaborador, tomate, atun, cliente):
    """Contado $13.500, fiado $6.000, abono $2.000, una anulada, una baja y un pedido."""

    def vender(quien, *lineas, cliente_id=None):
        return ventas.registrar_venta(
            usuario=quien, lineas=list(lineas), token=uuid.uuid4(), cliente_id=cliente_id
        )

    vender(colaborador, LineaNueva(atun.pk, 3, 4_500))
    vender(dueno, LineaNueva(tomate.pk, 2_000, 3_000), cliente_id=cliente.pk)
    anulada = vender(dueno, LineaNueva(atun.pk, 1, 4_500))
    ventas.anular_venta(por=dueno, venta_id=anulada.pk, motivo="Error")
    fiados.registrar_abono(dueno, cliente_id=cliente.pk, monto=2_000)
    corregir_existencia(dueno, producto_id=tomate.pk, nueva_cantidad=7_000, motivo="dano")
    proveedor = pedidos.crear_proveedor(dueno, "Proveedor A")
    pedido = pedidos.crear_pedido(
        dueno, producto_id=atun.pk, proveedor_id=proveedor.pk, cantidad=10, costo_unitario=3_900
    )
    pedidos.recibir_pedido(dueno, pedido_id=pedido.pk, cantidad_recibida=10, costo_unitario=3_900)


def test_calcular_dia(dia_con_movimiento):
    r = servicios.calcular_dia(hoy())
    assert r.cantidad_ventas == 2
    assert r.ventas_contado == 13_500
    assert r.ventas_fiado == 6_000
    assert r.anuladas == 1 and r.valor_anuladas == 4_500
    assert r.abonos == 2_000
    assert r.gastos_pedidos == 39_000
    assert r.mermas == 3_000  # 1 kg de tomate dañado a $3.000
    assert r.efectivo_esperado == 15_500
    assert {u["usuario__nombre"] for u in r.por_usuario} == {"Jean Carlo", "Esposa"}


def test_cierre_guarda_la_foto_y_es_unico(dueno, dia_con_movimiento):
    cierre = servicios.registrar_cierre(dueno, dia=hoy(), efectivo_contado=15_000)
    assert cierre.efectivo_esperado == 15_500
    assert cierre.diferencia == -500
    with pytest.raises(ReglaNegocio, match="ya fue cerrado"):
        servicios.registrar_cierre(dueno, dia=hoy(), efectivo_contado=15_500)


def test_cierre_requiere_permiso(colaborador):
    with pytest.raises(ReglaNegocio):
        servicios.registrar_cierre(colaborador, dia=hoy(), efectivo_contado=None)


def test_estadisticas(dia_con_movimiento):
    e = servicios.estadisticas(7)
    assert e.total == 19_500
    assert e.cantidad == 2
    assert e.ticket_promedio == 9_750
    assert len(e.por_dia) == 7
    assert e.por_dia[-1]["total"] == 19_500 and e.por_dia[-1]["porcentaje"] == 100
    assert e.productos[0]["producto__nombre"] == "Atún lata"  # $13.500 > $6.000
    assert e.por_cobrar == 4_000


def test_pantallas(cliente_web, dueno, dia_con_movimiento):
    web = cliente_web(dueno)
    assert "Efectivo que debería haber" in web.get(reverse("reportes:cierre")).content.decode()
    web.post(reverse("reportes:cerrar"), {"fecha": hoy().isoformat(), "efectivo_contado": "15.500"})
    assert "Cuadró" in web.get(reverse("reportes:cierre")).content.decode()
    for dias in (7, 30, 90, 1234):
        assert web.get(reverse("reportes:estadisticas"), {"dias": dias}).status_code == 200
