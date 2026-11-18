"""Única puerta para cambiar deudas de clientes: fiados, abonos y reversiones."""

from django.db import transaction
from django.db.models import F, OuterRef, QuerySet, Subquery, Sum

from apps.nucleo import servicios as nucleo
from apps.nucleo.dinero import formatear_pesos
from apps.nucleo.errores import ReglaNegocio
from apps.nucleo.texto import normalizar

from .models import Cliente, MovimientoFiado, TipoMovimientoFiado

# --- Consultas --------------------------------------------------------------


def buscar_clientes(texto: str, limite: int = 20) -> QuerySet[Cliente]:
    consulta = Cliente.objects.all()
    if texto := normalizar(texto or ""):
        consulta = consulta.filter(nombre_normalizado__contains=texto)
    return consulta.order_by("nombre")[:limite]


def crear_cliente(por, nombre: str, telefono: str = "") -> Cliente:
    if not (por.tiene_permiso("registrar_fiado") or por.tiene_permiso("ver_fiados")):
        raise ReglaNegocio("No tienes permiso para crear clientes de fiado.")
    nombre = " ".join((nombre or "").split())
    if not nombre:
        raise ReglaNegocio("Escribe el nombre del cliente.")
    cliente = Cliente.objects.create(nombre=nombre, telefono=(telefono or "").strip())
    nucleo.registrar(por, "fiados.crear_cliente", cliente=cliente.pk, nombre=nombre)
    return cliente


def _registrar(cliente_id: int, tipo: str, monto: int, usuario, origen: str) -> MovimientoFiado:
    if monto == 0:
        raise ReglaNegocio("El monto no puede ser cero.")
    with transaction.atomic():
        movimiento = MovimientoFiado.objects.create(
            cliente_id=cliente_id, tipo=tipo, monto=monto, usuario=usuario, origen=origen
        )
        Cliente.objects.filter(pk=cliente_id).update(saldo=F("saldo") + monto)
    return movimiento


def registrar_cargo(*, cliente_id: int, monto: int, usuario, origen: str) -> MovimientoFiado:
    if monto <= 0:
        raise ReglaNegocio("El valor fiado debe ser mayor que cero.")
    return _registrar(cliente_id, TipoMovimientoFiado.CARGO, monto, usuario, origen)


def revertir_cargo(*, cliente_id: int, monto: int, usuario, origen: str) -> MovimientoFiado:
    return _registrar(cliente_id, TipoMovimientoFiado.REVERSION, -abs(monto), usuario, origen)


def registrar_abono(por, *, cliente_id: int, monto: int) -> MovimientoFiado:
    """Pago parcial o total de la deuda. No se acepta más de lo que se debe."""
    if not por.tiene_permiso("ver_fiados"):
        raise ReglaNegocio("No tienes permiso para registrar abonos.")
    if monto <= 0:
        raise ReglaNegocio("El abono debe ser mayor que cero.")
    with transaction.atomic():
        saldo = Cliente.objects.values_list("saldo", flat=True).get(pk=cliente_id)
        if monto > saldo:
            raise ReglaNegocio(f"El abono supera la deuda ({_pesos(saldo)}).")
        movimiento = _registrar(cliente_id, TipoMovimientoFiado.ABONO, -monto, por, origen="abono")
        nucleo.registrar(por, "fiados.abono", cliente=cliente_id, monto=monto)
    return movimiento


def actualizar_cliente(por, cliente: Cliente, *, nombre: str, telefono: str) -> Cliente:
    if not por.tiene_permiso("ver_fiados"):
        raise ReglaNegocio("No tienes permiso para editar clientes.")
    nombre = " ".join((nombre or "").split())
    if not nombre:
        raise ReglaNegocio("Escribe el nombre del cliente.")
    cliente.nombre = nombre
    cliente.telefono = (telefono or "").strip()
    cliente.save(update_fields=["nombre", "nombre_normalizado", "telefono"])
    nucleo.registrar(por, "fiados.editar_cliente", cliente=cliente.pk)
    return cliente


def clientes_para_cobrar(texto: str = "", solo_con_deuda: bool = True) -> QuerySet[Cliente]:
    ultimo = (
        MovimientoFiado.objects.filter(cliente=OuterRef("pk"))
        .order_by("-fecha")
        .values("fecha")[:1]
    )
    consulta = Cliente.objects.annotate(ultimo_movimiento=Subquery(ultimo))
    if solo_con_deuda:
        consulta = consulta.filter(saldo__gt=0)
    if texto := normalizar(texto or ""):
        consulta = consulta.filter(nombre_normalizado__contains=texto)
    return consulta.order_by("-saldo", "nombre")


def total_por_cobrar() -> int:
    return Cliente.objects.filter(saldo__gt=0).aggregate(t=Sum("saldo"))["t"] or 0


def movimientos_de(cliente_id: int) -> QuerySet[MovimientoFiado]:
    return (
        MovimientoFiado.objects.filter(cliente_id=cliente_id)
        .select_related("usuario")
        .order_by("-fecha", "-id")
    )


def supera_limite(cliente: Cliente, monto_adicional: int, limite: int | None) -> bool:
    """El límite de deuda avisa, no bloquea (decisión del cliente)."""
    return bool(limite) and cliente.saldo + monto_adicional > limite


def _pesos(valor: int) -> str:
    return formatear_pesos(valor)
