"""Cierre del día y estadísticas. Solo leen datos de otras apps; el único dato
propio que escriben es el cierre guardado."""

from dataclasses import dataclass, field
from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.fiados.models import MovimientoFiado, TipoMovimientoFiado
from apps.fiados.servicios import total_por_cobrar
from apps.inventario.models import MotivoAjuste, MovimientoInventario, TipoMovimiento
from apps.nucleo import servicios as nucleo
from apps.nucleo.dinero import subtotal
from apps.nucleo.errores import ReglaNegocio
from apps.nucleo.fechas import hoy, rango_dia
from apps.pedidos.models import EstadoPedido, Pedido
from apps.ventas.models import LineaVenta, Venta

from .models import CierreDia


def _rango(desde: date, hasta: date):
    inicio, _ = rango_dia(desde)
    _, fin = rango_dia(hasta)
    return inicio, fin


def _valor_mermas(desde: date, hasta: date) -> int:
    """Valor a precio de venta de lo dado de baja por daño o pérdida."""
    inicio, fin = _rango(desde, hasta)
    bajas = MovimientoInventario.objects.filter(
        fecha__gte=inicio,
        fecha__lt=fin,
        tipo=TipoMovimiento.AJUSTE,
        motivo__in=[MotivoAjuste.DANO, MotivoAjuste.PERDIDA],
        cantidad__lt=0,
    ).select_related("producto")
    return sum(subtotal(m.producto.precio, -m.cantidad, m.producto.unidad) for m in bajas)


# --- Cierre del día ---------------------------------------------------------


@dataclass
class ResumenDia:
    fecha: date
    cantidad_ventas: int
    ventas_contado: int
    ventas_fiado: int
    anuladas: int
    valor_anuladas: int
    abonos: int
    gastos_pedidos: int
    mermas: int
    por_usuario: list[dict] = field(default_factory=list)

    @property
    def total_ventas(self) -> int:
        return self.ventas_contado + self.ventas_fiado

    @property
    def efectivo_esperado(self) -> int:
        """Lo que entró en efectivo: ventas de contado más abonos de fiados."""
        return self.ventas_contado + self.abonos


def calcular_dia(dia: date) -> ResumenDia:
    inicio, fin = rango_dia(dia)
    del_dia = Venta.objects.filter(fecha__gte=inicio, fecha__lt=fin)
    validas = del_dia.filter(anulada=False)
    totales = validas.aggregate(
        n=Count("id"),
        contado=Sum("total", filter=Q(es_fiado=False)),
        fiado=Sum("total", filter=Q(es_fiado=True)),
    )
    anuladas = del_dia.filter(anulada=True).aggregate(n=Count("id"), t=Sum("total"))
    abonos = MovimientoFiado.objects.filter(
        tipo=TipoMovimientoFiado.ABONO, fecha__gte=inicio, fecha__lt=fin
    ).aggregate(t=Sum("monto"))["t"]
    gastos = Pedido.objects.filter(estado=EstadoPedido.RECIBIDO, fecha_llegada=dia).aggregate(
        t=Sum("gasto")
    )["t"]
    por_usuario = list(
        validas.values("usuario__nombre")
        .annotate(n=Count("id"), suma=Sum("total"))
        .order_by("-suma")
    )
    return ResumenDia(
        fecha=dia,
        cantidad_ventas=totales["n"],
        ventas_contado=totales["contado"] or 0,
        ventas_fiado=totales["fiado"] or 0,
        anuladas=anuladas["n"],
        valor_anuladas=anuladas["t"] or 0,
        abonos=-(abonos or 0),
        gastos_pedidos=gastos or 0,
        mermas=_valor_mermas(dia, dia),
        por_usuario=por_usuario,
    )


def registrar_cierre(por, *, dia: date, efectivo_contado: int | None, nota: str = "") -> CierreDia:
    if not por.tiene_permiso("cierre_dia"):
        raise ReglaNegocio("No tienes permiso para cerrar el día.")
    if dia > hoy():
        raise ReglaNegocio("No se puede cerrar un día que no ha llegado.")
    if efectivo_contado is not None and efectivo_contado < 0:
        raise ReglaNegocio("El efectivo contado no puede ser negativo.")
    resumen = calcular_dia(dia)
    try:
        with transaction.atomic():
            cierre = CierreDia.objects.create(
                fecha=dia,
                cerrado_por=por,
                cantidad_ventas=resumen.cantidad_ventas,
                ventas_contado=resumen.ventas_contado,
                ventas_fiado=resumen.ventas_fiado,
                abonos=resumen.abonos,
                gastos_pedidos=resumen.gastos_pedidos,
                efectivo_esperado=resumen.efectivo_esperado,
                efectivo_contado=efectivo_contado,
                nota=" ".join((nota or "").split())[:300],
            )
    except IntegrityError as error:
        raise ReglaNegocio("Ese día ya fue cerrado.") from error
    nucleo.registrar(
        por,
        "reportes.cierre",
        fecha=dia.isoformat(),
        esperado=cierre.efectivo_esperado,
        contado=efectivo_contado,
    )
    return cierre


# --- Estadísticas -----------------------------------------------------------


@dataclass
class Estadisticas:
    desde: date
    hasta: date
    total: int
    cantidad: int
    fiado: int
    abonos: int
    gastos: int
    mermas: int
    por_cobrar: int
    por_dia: list[dict]
    productos: list[dict]
    por_usuario: list[dict]

    @property
    def ticket_promedio(self) -> int:
        return round(self.total / self.cantidad) if self.cantidad else 0


def estadisticas(dias: int = 30, hasta: date | None = None) -> Estadisticas:
    hasta = hasta or hoy()
    desde = hasta - timedelta(days=dias - 1)
    inicio, fin = _rango(desde, hasta)
    ventas = Venta.objects.filter(fecha__gte=inicio, fecha__lt=fin, anulada=False)
    totales = ventas.aggregate(
        suma=Sum("total"), n=Count("id"), fiado=Sum("total", filter=Q(es_fiado=True))
    )

    zona = timezone.get_current_timezone()
    por_fecha = {
        fila["dia"]: fila
        for fila in ventas.annotate(dia=TruncDate("fecha", tzinfo=zona))
        .values("dia")
        .annotate(suma=Sum("total"), n=Count("id"))
    }
    por_dia = []
    for i in range(dias):
        dia = desde + timedelta(days=i)
        fila = por_fecha.get(dia, {})
        por_dia.append({"dia": dia, "total": fila.get("suma") or 0, "n": fila.get("n") or 0})
    maximo = max((d["total"] for d in por_dia), default=0) or 1
    for d in por_dia:
        d["porcentaje"] = round(d["total"] * 100 / maximo)

    productos = list(
        LineaVenta.objects.filter(venta__in=ventas)
        .values("producto__nombre", "producto__unidad")
        .annotate(valor=Sum("subtotal"), cantidad=Sum("cantidad"), veces=Count("id"))
        .order_by("-valor")[:10]
    )
    por_usuario = list(
        ventas.values("usuario__nombre")
        .annotate(suma=Sum("total"), n=Count("id"))
        .order_by("-suma")
    )
    abonos = MovimientoFiado.objects.filter(
        tipo=TipoMovimientoFiado.ABONO, fecha__gte=inicio, fecha__lt=fin
    ).aggregate(t=Sum("monto"))["t"]
    gastos = Pedido.objects.filter(
        estado=EstadoPedido.RECIBIDO, fecha_llegada__gte=desde, fecha_llegada__lte=hasta
    ).aggregate(t=Sum("gasto"))["t"]
    return Estadisticas(
        desde=desde,
        hasta=hasta,
        total=totales["suma"] or 0,
        cantidad=totales["n"],
        fiado=totales["fiado"] or 0,
        abonos=-(abonos or 0),
        gastos=gastos or 0,
        mermas=_valor_mermas(desde, hasta),
        por_cobrar=total_por_cobrar(),
        por_dia=por_dia,
        productos=productos,
        por_usuario=por_usuario,
    )
