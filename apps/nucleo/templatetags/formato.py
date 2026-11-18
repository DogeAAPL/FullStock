from django import template
from django.utils import timezone

from apps.nucleo import cantidades
from apps.nucleo.dinero import formatear_pesos
from apps.nucleo.numeros import formatear_decimal

register = template.Library()


@register.filter
def pesos(valor) -> str:
    if valor is None or valor == "":
        return "—"
    return formatear_pesos(int(valor))


@register.filter
def cantidad(valor_base, unidad) -> str:
    """{{ producto.existencia|cantidad:producto.unidad }} -> "12,5 kg"."""
    if valor_base is None:
        return "—"
    return cantidades.formatear(int(valor_base), unidad)


@register.filter
def cantidad_editable(valor_base, unidad) -> str:
    """Valor para un campo de formulario, sin la unidad: 1500, kg -> "1,5"."""
    return formatear_decimal(cantidades.desde_base(int(valor_base), unidad))


@register.filter
def abreviatura(unidad) -> str:
    return cantidades.abreviatura(unidad)


@register.filter
def hora(valor) -> str:
    return timezone.localtime(valor).strftime("%H:%M") if valor else ""


@register.filter
def dia_mes(valor) -> str:
    return timezone.localtime(valor).strftime("%d/%m") if valor else ""


_ORIGENES = {"venta": "venta #{}", "anulacion": "anulación de la venta #{}", "pedido": "pedido #{}"}


@register.filter
def origen(valor: str) -> str:
    """ "venta:15" -> "venta #15". Lo que no se reconoce se muestra igual."""
    tipo, _, numero = (valor or "").partition(":")
    plantilla = _ORIGENES.get(tipo)
    return plantilla.format(numero) if plantilla and numero else valor
