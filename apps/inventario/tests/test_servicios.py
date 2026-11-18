from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.catalogo import servicios as catalogo
from apps.inventario import servicios
from apps.inventario.models import MotivoAjuste, MovimientoInventario, TipoMovimiento
from apps.nucleo.cantidades import Unidad
from apps.nucleo.errores import ReglaNegocio


def test_alta_con_cantidad_inicial_crea_movimiento(tomate):
    assert tomate.existencia == 10_000  # 10 kg en gramos
    movimiento = MovimientoInventario.objects.get(producto=tomate)
    assert movimiento.tipo == TipoMovimiento.INICIAL
    assert movimiento.cantidad == 10_000


def test_alta_sin_cantidad_no_crea_movimiento(crear_producto):
    producto = crear_producto("Arroz 500 g", Unidad.UNIDAD, 2500, existencia=None)
    assert producto.existencia == 0
    assert not MovimientoInventario.objects.filter(producto=producto).exists()


def test_producto_por_unidad_no_acepta_decimales(dueno):
    with pytest.raises(ReglaNegocio, match="unidades enteras"):
        servicios.dar_de_alta_producto(
            dueno, nombre="Atún", unidad=Unidad.UNIDAD, precio=4500, cantidad_inicial=Decimal("1.5")
        )


def test_crear_producto_requiere_permiso(colaborador):
    with pytest.raises(ReglaNegocio):
        catalogo.crear_producto(colaborador, "Tomate", Unidad.KILO, 3000)


def test_corregir_genera_ajuste_por_la_diferencia(dueno, tomate):
    servicios.corregir_existencia(
        dueno, producto_id=tomate.pk, nueva_cantidad=11_000, motivo=MotivoAjuste.CONTEO
    )
    servicios.corregir_existencia(
        dueno, producto_id=tomate.pk, nueva_cantidad=9_500, motivo=MotivoAjuste.DANO
    )
    tomate.refresh_from_db()
    assert tomate.existencia == 9_500
    ajustes = list(
        MovimientoInventario.objects.filter(producto=tomate, tipo=TipoMovimiento.AJUSTE)
        .order_by("id")
        .values_list("cantidad", "motivo")
    )
    assert ajustes == [(1_000, "conteo"), (-1_500, "dano")]


def test_corregir_misma_cantidad_o_sin_motivo(dueno, tomate):
    with pytest.raises(ReglaNegocio, match="igual"):
        servicios.corregir_existencia(
            dueno, producto_id=tomate.pk, nueva_cantidad=10_000, motivo="conteo"
        )
    with pytest.raises(ReglaNegocio, match="motivo"):
        servicios.corregir_existencia(dueno, producto_id=tomate.pk, nueva_cantidad=1, motivo="")


def test_corregir_requiere_permiso(crear_colaborador, tomate):
    sin_inventario = crear_colaborador(permisos={"vender"})
    with pytest.raises(ReglaNegocio):
        servicios.corregir_existencia(
            sin_inventario, producto_id=tomate.pk, nueva_cantidad=1, motivo="conteo"
        )


def test_movimientos_son_de_solo_insercion(tomate):
    movimiento = MovimientoInventario.objects.get(producto=tomate)
    with pytest.raises(IntegrityError), transaction.atomic():
        MovimientoInventario.objects.filter(pk=movimiento.pk).update(cantidad=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        MovimientoInventario.objects.filter(pk=movimiento.pk).delete()


def test_verificar_existencias_detecta_descuadre(tomate, atun):
    assert servicios.verificar_existencias() == []
    # Simula un error: alguien cambia la existencia sin movimiento.
    type(tomate).objects.filter(pk=tomate.pk).update(existencia=1)
    descuadres = servicios.verificar_existencias()
    assert [d.producto_id for d in descuadres] == [tomate.pk]
    assert descuadres[0].calculada == 10_000


def test_similares_avisa_duplicados(tomate, atun):
    assert catalogo.similares("tomate") == [tomate]
    assert catalogo.similares("ATUN") == [atun]
    assert catalogo.similares("Papa pastusa") == []
