"""Cantidades en enteros de la unidad mínima.

- Productos por unidad: se guardan en unidades.
- Productos por peso (kilo o libra): se guardan en gramos.

Así 1,5 kg se guarda como 1500 y nunca aparece un 1,4999999.
La libra se toma como 500 g, que es el uso colombiano.
"""

from decimal import Decimal

from django.db import models

from .numeros import formatear_decimal, redondear_entero


class Unidad(models.TextChoices):
    UNIDAD = "und", "Unidad"
    KILO = "kg", "Kilo (kg)"
    LIBRA = "lb", "Libra"


_FACTOR = {Unidad.UNIDAD: 1, Unidad.KILO: 1000, Unidad.LIBRA: 500}
_ABREVIATURA = {Unidad.UNIDAD: "und", Unidad.KILO: "kg", Unidad.LIBRA: "lb"}


def factor(unidad: Unidad | str) -> int:
    return _FACTOR[Unidad(unidad)]


def a_base(cantidad: Decimal, unidad: Unidad | str) -> int:
    """Cantidad escrita por el usuario (en la unidad del producto) -> unidad mínima."""
    unidad = Unidad(unidad)
    if unidad == Unidad.UNIDAD and cantidad != cantidad.to_integral_value():
        raise ValueError("Este producto se vende por unidades enteras.")
    return redondear_entero(cantidad * factor(unidad))


def desde_base(cantidad_base: int, unidad: Unidad | str) -> Decimal:
    return Decimal(cantidad_base) / factor(unidad)


def formatear(cantidad_base: int, unidad: Unidad | str) -> str:
    """1500, kg -> "1,5 kg"."""
    unidad = Unidad(unidad)
    return f"{formatear_decimal(desde_base(cantidad_base, unidad))} {_ABREVIATURA[unidad]}"


def abreviatura(unidad: Unidad | str) -> str:
    return _ABREVIATURA[Unidad(unidad)]
