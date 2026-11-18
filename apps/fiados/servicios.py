"""Única puerta para cambiar deudas de clientes.

Las pantallas de Fiados (lista de cobros, abonos) se construyen después; aquí
está lo que necesita una venta fiada.
"""

from django.db import transaction
from django.db.models import F, QuerySet

from apps.nucleo import servicios as nucleo
from apps.nucleo.errores import ReglaNegocio
from apps.nucleo.texto import normalizar

from .models import Cliente, MovimientoFiado, TipoMovimientoFiado


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
