"""Dinero en pesos enteros. Nunca se usa float para dinero."""

from decimal import Decimal

from .cantidades import Unidad, factor
from .numeros import formatear_decimal, leer_numero, redondear_entero


def leer_pesos(texto: str | int) -> int:
    """Lee un valor en pesos ("$ 3.000", "3000") y lo redondea al peso."""
    return redondear_entero(leer_numero(texto))


def subtotal(precio: int, cantidad_base: int, unidad: Unidad | str) -> int:
    """Precio por unidad de venta × cantidad guardada en la unidad mínima.

    Ejemplo: tomate a $3.000 el kilo, 1500 g -> $4.500.
    """
    return redondear_entero(Decimal(precio) * cantidad_base / factor(unidad))


def formatear_pesos(valor: int) -> str:
    """27500 -> "$ 27.500"."""
    return f"$ {formatear_decimal(valor, max_decimales=0)}"
