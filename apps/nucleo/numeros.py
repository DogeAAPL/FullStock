"""Lectura y formato de números en formato colombiano.

En Colombia el punto separa miles y la coma separa decimales: "1.500" son mil
quinientos y "1,5" es uno y medio. Todos los formularios y la carga de archivos
deben leer números con `leer_numero` para que no haya dos interpretaciones.
"""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_MILES_CON_PUNTO = re.compile(r"^\d{1,3}(\.\d{3})+$")


def leer_numero(texto: str | int | Decimal) -> Decimal:
    """Convierte texto en formato colombiano a Decimal. Rechaza vacíos y negativos.

    Reglas:
    - "1.500" -> 1500 (punto como separador de miles)
    - "1,5" -> 1.5 y "1.500,5" -> 1500.5
    - "1.5" -> 1.5 (un punto que no separa miles se toma como decimal)
    """
    if isinstance(texto, int | Decimal):
        valor = Decimal(texto)
    else:
        limpio = texto.replace("$", "").replace(" ", "").strip()
        if not limpio:
            raise ValueError("Escribe un número.")
        if "," in limpio:
            limpio = limpio.replace(".", "").replace(",", ".")
        elif _MILES_CON_PUNTO.match(limpio):
            limpio = limpio.replace(".", "")
        try:
            valor = Decimal(limpio)
        except InvalidOperation as error:
            raise ValueError(f"«{texto}» no es un número válido.") from error
    if not valor.is_finite():
        raise ValueError("Escribe un número.")
    if valor < 0:
        raise ValueError("El número no puede ser negativo.")
    return valor


def redondear_entero(valor: Decimal) -> int:
    """Redondeo comercial al entero más cercano (0,5 sube)."""
    return int(valor.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def formatear_decimal(valor: Decimal | int, max_decimales: int = 3) -> str:
    """1500.5 -> "1.500,5"; 12 -> "12". Sin ceros sobrantes a la derecha."""
    valor = Decimal(valor)
    cuantizado = valor.quantize(Decimal(1).scaleb(-max_decimales), rounding=ROUND_HALF_UP)
    entero, _, decimales = f"{abs(cuantizado):f}".partition(".")
    decimales = decimales.rstrip("0")
    entero = f"{int(entero):,}".replace(",", ".")
    signo = "-" if cuantizado < 0 else ""
    return f"{signo}{entero},{decimales}" if decimales else f"{signo}{entero}"
