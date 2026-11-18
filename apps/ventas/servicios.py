"""Registrar, anular y corregir ventas."""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, QuerySet, Sum
from django.utils import timezone

from apps.catalogo.models import Producto
from apps.fiados import servicios as fiados
from apps.inventario import servicios as inventario
from apps.inventario.models import TipoMovimiento
from apps.nucleo import cantidades
from apps.nucleo import servicios as nucleo
from apps.nucleo.dinero import subtotal
from apps.nucleo.errores import ReglaNegocio
from apps.nucleo.fechas import rango_dia
from apps.nucleo.models import Configuracion

from .models import LineaVenta, Venta


@dataclass(frozen=True)
class LineaNueva:
    producto_id: int
    cantidad: int  # unidad mínima
    precio: int  # por unidad de venta


def registrar_venta(
    *,
    usuario,
    lineas: list[LineaNueva],
    token: uuid.UUID,
    cliente_id: int | None = None,
    corrige_a: Venta | None = None,
) -> Venta:
    """Guarda la venta, descuenta inventario y, si es fiada, carga la deuda al cliente.

    Idempotente por `token`: si ya se guardó una venta con ese token, la devuelve.
    """
    if existente := Venta.objects.filter(token=token).first():
        return existente
    try:
        with transaction.atomic():
            return _registrar(usuario, lineas, token, cliente_id, corrige_a)
    except IntegrityError:
        # Dos envíos casi simultáneos del mismo formulario: el segundo choca con el token.
        if existente := Venta.objects.filter(token=token).first():
            return existente
        raise


def _registrar(usuario, lineas, token, cliente_id, corrige_a) -> Venta:
    if not usuario.tiene_permiso("vender"):
        raise ReglaNegocio("No tienes permiso para vender.")
    if not lineas:
        raise ReglaNegocio("La venta no tiene productos.")
    if cliente_id is not None and not usuario.tiene_permiso("registrar_fiado"):
        raise ReglaNegocio("No tienes permiso para registrar ventas fiadas.")
    if any(linea.cantidad <= 0 for linea in lineas):
        raise ReglaNegocio("Todas las cantidades deben ser mayores que cero.")

    productos = Producto.objects.in_bulk({linea.producto_id for linea in lineas})
    if len(productos) != len({linea.producto_id for linea in lineas}):
        raise ReglaNegocio("Uno de los productos ya no existe.")
    _validar_existencia(lineas, productos)

    venta = Venta.objects.create(
        usuario=usuario,
        token=token,
        es_fiado=cliente_id is not None,
        cliente_id=cliente_id,
        corrige_a=corrige_a,
    )
    nuevas = [
        LineaVenta(
            venta=venta,
            producto_id=linea.producto_id,
            cantidad=linea.cantidad,
            precio=linea.precio,
            subtotal=subtotal(linea.precio, linea.cantidad, productos[linea.producto_id].unidad),
        )
        for linea in lineas
    ]
    LineaVenta.objects.bulk_create(nuevas)
    venta.total = sum(linea.subtotal for linea in nuevas)
    venta.save(update_fields=["total"])

    origen = f"venta:{venta.pk}"
    for linea in nuevas:
        inventario.registrar_movimiento(
            producto_id=linea.producto_id,
            tipo=TipoMovimiento.VENTA,
            cantidad=-linea.cantidad,
            usuario=usuario,
            origen=origen,
        )
    if cliente_id is not None and venta.total > 0:
        fiados.registrar_cargo(
            cliente_id=cliente_id, monto=venta.total, usuario=usuario, origen=origen
        )
    nucleo.registrar(usuario, "ventas.registrar", venta=venta.pk, total=venta.total)
    return venta


def _validar_existencia(lineas: list[LineaNueva], productos: dict[int, Producto]) -> None:
    if Configuracion.cargar().vender_sin_existencia:
        return
    pedido: dict[int, int] = defaultdict(int)
    for linea in lineas:
        pedido[linea.producto_id] += linea.cantidad
    for producto_id, cantidad in pedido.items():
        producto = productos[producto_id]
        if producto.existencia < cantidad:
            disponible = cantidades.formatear(max(producto.existencia, 0), producto.unidad)
            raise ReglaNegocio(f"No hay suficiente «{producto.nombre}» registrado ({disponible}).")


@transaction.atomic
def anular_venta(*, por, venta_id: int, motivo: str) -> Venta:
    """Marca la venta como anulada y devuelve inventario y deuda con movimientos nuevos."""
    if not por.tiene_permiso("anular_ventas"):
        raise ReglaNegocio("No tienes permiso para anular ventas.")
    motivo = " ".join((motivo or "").split())
    if not motivo:
        raise ReglaNegocio("Escribe el motivo de la anulación.")
    # Actualización condicional: si dos personas anulan a la vez, solo una lo logra.
    actualizadas = Venta.objects.filter(pk=venta_id, anulada=False).update(
        anulada=True, anulada_por=por, anulada_en=timezone.now(), motivo_anulacion=motivo[:200]
    )
    if not actualizadas:
        raise ReglaNegocio("La venta ya estaba anulada o no existe.")
    venta = Venta.objects.get(pk=venta_id)
    origen = f"anulacion:{venta.pk}"
    for linea in venta.lineas.all():
        inventario.registrar_movimiento(
            producto_id=linea.producto_id,
            tipo=TipoMovimiento.ANULACION_VENTA,
            cantidad=linea.cantidad,
            usuario=por,
            origen=origen,
        )
    if venta.es_fiado and venta.total > 0:
        fiados.revertir_cargo(
            cliente_id=venta.cliente_id, monto=venta.total, usuario=por, origen=origen
        )
    nucleo.registrar(por, "ventas.anular", venta=venta.pk, motivo=motivo)
    return venta


def corregir_venta(
    *,
    por,
    venta_id: int,
    lineas: list[LineaNueva],
    token: uuid.UUID,
    cliente_id: int | None = None,
) -> Venta:
    """Para el usuario es "editar"; en los datos, anula la original y crea una nueva enlazada."""
    if existente := Venta.objects.filter(token=token).first():
        return existente
    with transaction.atomic():
        original = Venta.objects.get(pk=venta_id)
        anular_venta(por=por, venta_id=venta_id, motivo="Corrección de la venta")
        return registrar_venta(
            usuario=por, lineas=lineas, token=token, cliente_id=cliente_id, corrige_a=original
        )


def ventas_del_dia(dia: date) -> QuerySet[Venta]:
    inicio, fin = rango_dia(dia)
    return (
        Venta.objects.filter(fecha__gte=inicio, fecha__lt=fin)
        .select_related("usuario", "cliente", "anulada_por")
        .prefetch_related(
            Prefetch("lineas", queryset=LineaVenta.objects.select_related("producto"))
        )
        .order_by("fecha")
    )


def resumen_del_dia(dia: date) -> dict:
    inicio, fin = rango_dia(dia)
    validas = Venta.objects.filter(fecha__gte=inicio, fecha__lt=fin, anulada=False)
    datos = validas.aggregate(cantidad=Count("id"), total=Sum("total"))
    fiado = validas.filter(es_fiado=True).aggregate(total=Sum("total"))["total"]
    return {"cantidad": datos["cantidad"], "total": datos["total"] or 0, "fiado": fiado or 0}
