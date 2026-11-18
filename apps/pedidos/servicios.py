"""Pedidos a proveedores: crear, recibir (suma al inventario) y cancelar."""

from datetime import date

from django.db import transaction
from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from apps.catalogo.models import Producto
from apps.inventario import servicios as inventario
from apps.inventario.models import TipoMovimiento
from apps.nucleo import servicios as nucleo
from apps.nucleo.dinero import subtotal
from apps.nucleo.errores import ReglaNegocio
from apps.nucleo.fechas import hoy
from apps.nucleo.texto import normalizar

from .models import EstadoPedido, Pedido, Proveedor

# --- Proveedores ------------------------------------------------------------


def proveedores_con_pendientes() -> QuerySet[Proveedor]:
    return Proveedor.objects.annotate(
        pendientes=Count("pedidos", filter=Q(pedidos__estado=EstadoPedido.PENDIENTE))
    ).order_by("nombre")


def proveedores_con_mismo_nombre(nombre: str) -> list[Proveedor]:
    buscado = normalizar(nombre or "")
    if not buscado:
        return []
    return list(Proveedor.objects.filter(nombre_normalizado=buscado))


def crear_proveedor(por, nombre: str, telefono: str = "") -> Proveedor:
    if not por.tiene_permiso("proveedores"):
        raise ReglaNegocio("No tienes permiso para registrar proveedores.")
    nombre = " ".join((nombre or "").split())
    if not nombre:
        raise ReglaNegocio("Escribe el nombre del proveedor.")
    proveedor = Proveedor.objects.create(nombre=nombre, telefono=(telefono or "").strip())
    nucleo.registrar(por, "pedidos.crear_proveedor", proveedor=proveedor.pk, nombre=nombre)
    return proveedor


# --- Pedidos ----------------------------------------------------------------


def pendientes() -> QuerySet[Pedido]:
    return (
        Pedido.objects.filter(estado=EstadoPedido.PENDIENTE)
        .select_related("producto", "proveedor", "creado_por")
        .order_by("fecha_pedido", "id")
    )


def pendientes_de(producto_id: int) -> QuerySet[Pedido]:
    """Para el aviso "ya pediste este producto" (no bloquea)."""
    return pendientes().filter(producto_id=producto_id)


def historial(limite: int = 50) -> QuerySet[Pedido]:
    return (
        Pedido.objects.exclude(estado=EstadoPedido.PENDIENTE)
        .select_related("producto", "proveedor", "recibido_por", "cancelado_por")
        .order_by("-id")[:limite]
    )


def crear_pedido(
    por,
    *,
    producto_id: int,
    proveedor_id: int,
    cantidad: int,
    costo_unitario: int,
    fecha_pedido: date | None = None,
) -> Pedido:
    if not por.tiene_permiso("pedidos"):
        raise ReglaNegocio("No tienes permiso para hacer pedidos.")
    if cantidad <= 0:
        raise ReglaNegocio("La cantidad debe ser mayor que cero.")
    if costo_unitario < 0:
        raise ReglaNegocio("El costo no puede ser negativo.")
    fecha_pedido = fecha_pedido or hoy()
    if fecha_pedido > hoy():
        raise ReglaNegocio("La fecha del pedido no puede ser futura.")
    if not Producto.objects.filter(pk=producto_id, activo=True).exists():
        raise ReglaNegocio("Elige un producto.")
    if not Proveedor.objects.filter(pk=proveedor_id).exists():
        raise ReglaNegocio("Elige un proveedor.")
    pedido = Pedido.objects.create(
        producto_id=producto_id,
        proveedor_id=proveedor_id,
        cantidad=cantidad,
        costo_unitario=costo_unitario,
        fecha_pedido=fecha_pedido,
        creado_por=por,
    )
    nucleo.registrar(por, "pedidos.crear", pedido=pedido.pk)
    return pedido


@transaction.atomic
def recibir_pedido(
    por,
    *,
    pedido_id: int,
    cantidad_recibida: int,
    costo_unitario: int,
    fecha_llegada: date | None = None,
) -> Pedido:
    """Cierra el pedido y suma al inventario lo que llegó. Solo una vez por pedido."""
    if not por.tiene_permiso("pedidos"):
        raise ReglaNegocio("No tienes permiso para recibir pedidos.")
    if cantidad_recibida <= 0:
        raise ReglaNegocio("La cantidad recibida debe ser mayor que cero.")
    if costo_unitario < 0:
        raise ReglaNegocio("El costo no puede ser negativo.")
    pedido = Pedido.objects.select_related("producto").get(pk=pedido_id)
    fecha_llegada = fecha_llegada or hoy()
    if fecha_llegada < pedido.fecha_pedido or fecha_llegada > hoy():
        raise ReglaNegocio("La fecha de llegada debe estar entre la del pedido y hoy.")
    gasto = subtotal(costo_unitario, cantidad_recibida, pedido.producto.unidad)
    # Actualización condicional: un pedido solo se recibe una vez aunque dos
    # personas confirmen al mismo tiempo.
    actualizados = Pedido.objects.filter(pk=pedido_id, estado=EstadoPedido.PENDIENTE).update(
        estado=EstadoPedido.RECIBIDO,
        cantidad_recibida=cantidad_recibida,
        costo_recibido=costo_unitario,
        gasto=gasto,
        fecha_llegada=fecha_llegada,
        recibido_por=por,
        recibido_en=timezone.now(),
    )
    if not actualizados:
        raise ReglaNegocio("Este pedido ya fue recibido o cancelado.")
    inventario.registrar_movimiento(
        producto_id=pedido.producto_id,
        tipo=TipoMovimiento.RECEPCION,
        cantidad=cantidad_recibida,
        usuario=por,
        origen=f"pedido:{pedido.pk}",
    )
    nucleo.registrar(
        por, "pedidos.recibir", pedido=pedido.pk, cantidad=cantidad_recibida, gasto=gasto
    )
    pedido.refresh_from_db()
    return pedido


@transaction.atomic
def cancelar_pedido(por, *, pedido_id: int) -> Pedido:
    if not por.tiene_permiso("pedidos"):
        raise ReglaNegocio("No tienes permiso para cancelar pedidos.")
    actualizados = Pedido.objects.filter(pk=pedido_id, estado=EstadoPedido.PENDIENTE).update(
        estado=EstadoPedido.CANCELADO, cancelado_por=por, cancelado_en=timezone.now()
    )
    if not actualizados:
        raise ReglaNegocio("Este pedido ya fue recibido o cancelado.")
    nucleo.registrar(por, "pedidos.cancelar", pedido=pedido_id)
    return Pedido.objects.get(pk=pedido_id)
