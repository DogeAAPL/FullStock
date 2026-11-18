import random
import uuid

import pytest
from django.db.models import Sum

from apps.catalogo.models import Producto
from apps.fiados.models import Cliente, MovimientoFiado
from apps.inventario.models import MovimientoInventario
from apps.inventario.servicios import corregir_existencia, verificar_existencias
from apps.nucleo.errores import ReglaNegocio
from apps.nucleo.servicios import actualizar_configuracion
from apps.usuarios.servicios import asignar_permisos
from apps.ventas import servicios
from apps.ventas.models import Venta
from apps.ventas.servicios import LineaNueva


def _vender(usuario, *lineas, cliente_id=None, token=None):
    return servicios.registrar_venta(
        usuario=usuario, lineas=list(lineas), token=token or uuid.uuid4(), cliente_id=cliente_id
    )


def test_venta_calcula_total_y_descuenta_inventario(colaborador, tomate, atun):
    venta = _vender(
        colaborador,
        LineaNueva(tomate.pk, 1_500, 3_000),  # 1,5 kg
        LineaNueva(atun.pk, 2, 4_500),
    )
    assert venta.total == 4_500 + 9_000
    assert venta.usuario == colaborador
    tomate.refresh_from_db()
    atun.refresh_from_db()
    assert tomate.existencia == 8_500
    assert atun.existencia == 18


def test_precio_cobrado_se_guarda_en_la_linea(colaborador, tomate):
    venta = _vender(colaborador, LineaNueva(tomate.pk, 1_000, 2_800))  # rebaja
    assert venta.lineas.get().precio == 2_800
    assert venta.total == 2_800


def test_doble_clic_no_duplica_la_venta(colaborador, tomate):
    token = uuid.uuid4()
    primera = _vender(colaborador, LineaNueva(tomate.pk, 1_000, 3_000), token=token)
    segunda = _vender(colaborador, LineaNueva(tomate.pk, 1_000, 3_000), token=token)
    assert primera.pk == segunda.pk
    assert Venta.objects.count() == 1
    tomate.refresh_from_db()
    assert tomate.existencia == 9_000


def test_venta_vacia_o_cantidad_cero(colaborador, tomate):
    with pytest.raises(ReglaNegocio):
        _vender(colaborador)
    with pytest.raises(ReglaNegocio):
        _vender(colaborador, LineaNueva(tomate.pk, 0, 3_000))


def test_venta_sin_existencia_permitida_por_defecto(colaborador, tomate):
    _vender(colaborador, LineaNueva(tomate.pk, 12_000, 3_000))
    tomate.refresh_from_db()
    assert tomate.existencia == -2_000


def test_el_dueno_puede_bloquear_ventas_sin_existencia(dueno, colaborador, tomate):
    actualizar_configuracion(dueno, {"vender_sin_existencia": False})
    with pytest.raises(ReglaNegocio, match="No hay suficiente"):
        _vender(
            colaborador, LineaNueva(tomate.pk, 6_000, 3_000), LineaNueva(tomate.pk, 6_000, 3_000)
        )
    assert Venta.objects.count() == 0


def test_venta_fiada_carga_la_deuda(colaborador, tomate, cliente):
    venta = _vender(colaborador, LineaNueva(tomate.pk, 2_000, 3_000), cliente_id=cliente.pk)
    cliente.refresh_from_db()
    assert venta.es_fiado
    assert cliente.saldo == 6_000


def test_fiar_requiere_permiso(crear_colaborador, tomate, cliente):
    sin_fiado = crear_colaborador(permisos={"vender"})
    with pytest.raises(ReglaNegocio):
        _vender(sin_fiado, LineaNueva(tomate.pk, 1_000, 3_000), cliente_id=cliente.pk)


# --- Anular y corregir ------------------------------------------------------


def test_anular_devuelve_inventario_y_deuda(dueno, colaborador, tomate, cliente):
    venta = _vender(colaborador, LineaNueva(tomate.pk, 2_000, 3_000), cliente_id=cliente.pk)
    servicios.anular_venta(por=dueno, venta_id=venta.pk, motivo="Se registró dos veces")
    venta.refresh_from_db()
    tomate.refresh_from_db()
    cliente.refresh_from_db()
    assert venta.anulada and venta.anulada_por == dueno
    assert tomate.existencia == 10_000
    assert cliente.saldo == 0
    # La historia se conserva: venta + anulación.
    origenes = [f"venta:{venta.pk}", f"anulacion:{venta.pk}"]
    assert MovimientoInventario.objects.filter(origen__in=origenes).count() == 2


def test_no_se_anula_dos_veces(dueno, colaborador, tomate):
    venta = _vender(colaborador, LineaNueva(tomate.pk, 1_000, 3_000))
    servicios.anular_venta(por=dueno, venta_id=venta.pk, motivo="Error")
    with pytest.raises(ReglaNegocio, match="ya estaba anulada"):
        servicios.anular_venta(por=dueno, venta_id=venta.pk, motivo="Error")
    tomate.refresh_from_db()
    assert tomate.existencia == 10_000


def test_anular_requiere_permiso_y_motivo(dueno, colaborador, tomate):
    venta = _vender(colaborador, LineaNueva(tomate.pk, 1_000, 3_000))
    with pytest.raises(ReglaNegocio, match="permiso"):
        servicios.anular_venta(por=colaborador, venta_id=venta.pk, motivo="x")
    with pytest.raises(ReglaNegocio, match="motivo"):
        servicios.anular_venta(por=dueno, venta_id=venta.pk, motivo="  ")


def test_permiso_de_anular_activado_por_el_dueno(dueno, colaborador, tomate):
    venta = _vender(colaborador, LineaNueva(tomate.pk, 1_000, 3_000))
    asignar_permisos(dueno, colaborador, {"vender", "anular_ventas"})
    servicios.anular_venta(por=colaborador, venta_id=venta.pk, motivo="Cliente devolvió")
    assert Venta.objects.get(pk=venta.pk).anulada


def test_corregir_anula_la_original_y_crea_una_enlazada(dueno, colaborador, tomate, atun):
    original = _vender(colaborador, LineaNueva(tomate.pk, 1_000, 3_000))
    nueva = servicios.corregir_venta(
        por=dueno,
        venta_id=original.pk,
        lineas=[LineaNueva(atun.pk, 2, 4_500)],
        token=uuid.uuid4(),
    )
    original.refresh_from_db()
    tomate.refresh_from_db()
    atun.refresh_from_db()
    assert original.anulada
    assert nueva.corrige_a == original
    assert tomate.existencia == 10_000
    assert atun.existencia == 18


def test_resumen_del_dia_excluye_anuladas(dueno, colaborador, tomate, cliente):
    _vender(colaborador, LineaNueva(tomate.pk, 1_000, 3_000))
    _vender(colaborador, LineaNueva(tomate.pk, 1_000, 3_000), cliente_id=cliente.pk)
    anulada = _vender(colaborador, LineaNueva(tomate.pk, 1_000, 3_000))
    servicios.anular_venta(por=dueno, venta_id=anulada.pk, motivo="Error")
    from apps.nucleo.fechas import hoy

    assert servicios.resumen_del_dia(hoy()) == {"cantidad": 2, "total": 6_000, "fiado": 3_000}


# --- Invariante -------------------------------------------------------------


def test_invariante_existencias_y_saldos_tras_operaciones_al_azar(dueno, crear_producto, cliente):
    """Tras cualquier mezcla de ventas, anulaciones, correcciones y ajustes, la
    existencia guardada es la suma de movimientos y el saldo, la de cargos y abonos."""
    azar = random.Random(20261118)
    productos = [crear_producto(f"Producto {i}", "kg", 1_000 + i, "50") for i in range(4)]
    ventas: list[Venta] = []
    for _ in range(60):
        operacion = azar.choice(["vender", "vender", "fiar", "anular", "corregir", "ajustar"])
        if operacion in {"vender", "fiar"}:
            lineas = [
                LineaNueva(p.pk, azar.randint(1, 3_000), p.precio)
                for p in azar.sample(productos, azar.randint(1, 3))
            ]
            ventas.append(
                _vender(dueno, *lineas, cliente_id=cliente.pk if operacion == "fiar" else None)
            )
        elif operacion == "anular" and ventas:
            venta = azar.choice(ventas)
            if not Venta.objects.get(pk=venta.pk).anulada:
                servicios.anular_venta(por=dueno, venta_id=venta.pk, motivo="prueba")
        elif operacion == "corregir" and ventas:
            venta = azar.choice(ventas)
            if not Venta.objects.get(pk=venta.pk).anulada:
                p = azar.choice(productos)
                ventas.append(
                    servicios.corregir_venta(
                        por=dueno,
                        venta_id=venta.pk,
                        lineas=[LineaNueva(p.pk, azar.randint(1, 2_000), p.precio)],
                        token=uuid.uuid4(),
                        cliente_id=venta.cliente_id,
                    )
                )
        elif operacion == "ajustar":
            p = azar.choice(productos)
            nueva = azar.randint(0, 60_000)
            if Producto.objects.get(pk=p.pk).existencia != nueva:
                corregir_existencia(dueno, producto_id=p.pk, nueva_cantidad=nueva, motivo="conteo")

    assert verificar_existencias() == []
    cliente.refresh_from_db()
    suma = MovimientoFiado.objects.filter(cliente=cliente).aggregate(s=Sum("monto"))["s"] or 0
    assert cliente.saldo == suma
    fiado_vigente = (
        Venta.objects.filter(cliente=cliente, anulada=False).aggregate(s=Sum("total"))["s"] or 0
    )
    assert cliente.saldo == fiado_vigente
    assert Cliente.objects.count() == 1
