from decimal import Decimal

import pytest

from apps.nucleo import cantidades
from apps.nucleo.cantidades import Unidad
from apps.nucleo.dinero import formatear_pesos, leer_pesos, subtotal
from apps.nucleo.numeros import formatear_decimal, leer_numero
from apps.nucleo.texto import normalizar


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("1,5", Decimal("1.5")),
        ("1.500", Decimal("1500")),
        ("1.500,5", Decimal("1500.5")),
        ("1.250.000", Decimal("1250000")),
        ("1.5", Decimal("1.5")),
        ("$ 3.000", Decimal("3000")),
        (" 12 ", Decimal("12")),
        ("0,25", Decimal("0.25")),
    ],
)
def test_leer_numero_formato_colombiano(texto, esperado):
    assert leer_numero(texto) == esperado


@pytest.mark.parametrize("texto", ["", "abc", "-3", "1,2,3", "NaN", "Infinity"])
def test_leer_numero_rechaza_invalidos(texto):
    with pytest.raises(ValueError):
        leer_numero(texto)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [(Decimal("1500.5"), "1.500,5"), (12, "12"), (Decimal("0.250"), "0,25"), (-1500, "-1.500")],
)
def test_formatear_decimal(valor, esperado):
    assert formatear_decimal(valor) == esperado


def test_pesos():
    assert leer_pesos("$ 27.500") == 27500
    assert leer_pesos("3.000,5") == 3001  # redondeo comercial
    assert formatear_pesos(27500) == "$ 27.500"


@pytest.mark.parametrize(
    ("precio", "cantidad", "unidad", "esperado"),
    [
        (3000, 1500, Unidad.KILO, 4500),  # 1,5 kg de tomate
        (4500, 2, Unidad.UNIDAD, 9000),  # 2 latas de atún
        (2000, 750, Unidad.LIBRA, 3000),  # 1,5 lb
        (999, 333, Unidad.KILO, 333),  # 332,667 -> 333
    ],
)
def test_subtotal(precio, cantidad, unidad, esperado):
    assert subtotal(precio, cantidad, unidad) == esperado


def test_cantidades_en_unidad_minima():
    assert cantidades.a_base(Decimal("1.5"), Unidad.KILO) == 1500
    assert cantidades.a_base(Decimal("2"), Unidad.LIBRA) == 1000
    assert cantidades.a_base(Decimal("3"), Unidad.UNIDAD) == 3
    assert cantidades.formatear(1500, Unidad.KILO) == "1,5 kg"
    assert cantidades.formatear(24, Unidad.UNIDAD) == "24 und"


def test_unidades_enteras():
    with pytest.raises(ValueError, match="unidades enteras"):
        cantidades.a_base(Decimal("1.5"), Unidad.UNIDAD)


def test_normalizar():
    assert normalizar("  Atún   LATA ") == "atun lata"
    assert normalizar("Cebolla Cabezona") == "cebolla cabezona"
