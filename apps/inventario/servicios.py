"""Única puerta para cambiar el inventario.

Toda entrada o salida pasa por `registrar_movimiento`, que inserta el
movimiento y actualiza la existencia en la misma transacción. Otras apps
(ventas, pedidos) llaman a estas funciones; nunca escriben las tablas directo.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Sum

from apps.catalogo import servicios as catalogo
from apps.catalogo.models import Producto
from apps.nucleo import servicios as nucleo
from apps.nucleo.cantidades import a_base
from apps.nucleo.errores import ReglaNegocio

from .models import MotivoAjuste, MovimientoInventario, TipoMovimiento


def registrar_movimiento(
    *,
    producto_id: int,
    tipo: TipoMovimiento,
    cantidad: int,
    usuario,
    motivo: str = "",
    origen: str = "",
) -> MovimientoInventario:
    if cantidad == 0:
        raise ReglaNegocio("La cantidad del movimiento no puede ser cero.")
    with transaction.atomic():
        movimiento = MovimientoInventario.objects.create(
            producto_id=producto_id,
            tipo=tipo,
            cantidad=cantidad,
            usuario=usuario,
            motivo=motivo,
            origen=origen,
        )
        Producto.objects.filter(pk=producto_id).update(existencia=F("existencia") + cantidad)
    return movimiento


@transaction.atomic
def dar_de_alta_producto(
    por, *, nombre: str, unidad: str, precio: int, cantidad_inicial: Decimal | None = None
) -> Producto:
    producto = catalogo.crear_producto(por, nombre, unidad, precio)
    if cantidad_inicial:
        try:
            base = a_base(cantidad_inicial, unidad)
        except ValueError as error:
            raise ReglaNegocio(str(error)) from error
        if base:
            registrar_movimiento(
                producto_id=producto.pk,
                tipo=TipoMovimiento.INICIAL,
                cantidad=base,
                usuario=por,
                origen=f"producto:{producto.pk}",
            )
            producto.refresh_from_db(fields=["existencia"])
    return producto


@transaction.atomic
def corregir_existencia(
    por, *, producto_id: int, nueva_cantidad: int, motivo: str
) -> MovimientoInventario:
    """Lleva la existencia registrada a `nueva_cantidad` (unidad mínima) con un ajuste."""
    if not por.tiene_permiso("inventario"):
        raise ReglaNegocio("No tienes permiso para corregir el inventario.")
    if motivo not in MotivoAjuste.values:
        raise ReglaNegocio("Elige el motivo de la corrección.")
    if nueva_cantidad < 0:
        raise ReglaNegocio("La cantidad no puede ser negativa.")
    actual = Producto.objects.values_list("existencia", flat=True).get(pk=producto_id)
    diferencia = nueva_cantidad - actual
    if diferencia == 0:
        raise ReglaNegocio("La cantidad nueva es igual a la registrada.")
    movimiento = registrar_movimiento(
        producto_id=producto_id,
        tipo=TipoMovimiento.AJUSTE,
        cantidad=diferencia,
        usuario=por,
        motivo=motivo,
        origen=f"ajuste:{motivo}",
    )
    nucleo.registrar(
        por,
        "inventario.correccion",
        producto=producto_id,
        antes=actual,
        despues=nueva_cantidad,
        motivo=motivo,
    )
    return movimiento


@dataclass(frozen=True)
class Descuadre:
    producto_id: int
    nombre: str
    guardada: int
    calculada: int


def verificar_existencias() -> list[Descuadre]:
    """Compara la existencia guardada con la suma de movimientos de cada producto."""
    sumas = dict(
        MovimientoInventario.objects.values("producto")
        .annotate(total=Sum("cantidad"))
        .values_list("producto", "total")
    )
    return [
        Descuadre(p.pk, p.nombre, p.existencia, sumas.get(p.pk, 0))
        for p in Producto.objects.only("id", "nombre", "existencia")
        if p.existencia != sumas.get(p.pk, 0)
    ]
