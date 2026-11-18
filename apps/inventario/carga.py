"""Carga de productos desde un archivo de Excel (.xlsx) o CSV.

Primero se revisa el archivo y se muestra qué pasará con cada fila; los
productos solo se crean cuando la persona confirma. Columnas: nombre, unidad,
precio y, opcional, cantidad inicial.
"""

import csv
import io
from dataclasses import asdict, dataclass, field
from decimal import Decimal

from django.db import transaction
from openpyxl import Workbook, load_workbook

from apps.catalogo import servicios as catalogo
from apps.nucleo.cantidades import Unidad, a_base
from apps.nucleo.dinero import leer_pesos
from apps.nucleo.errores import ReglaNegocio
from apps.nucleo.numeros import leer_numero
from apps.nucleo.texto import normalizar

from . import servicios

TAMANO_MAXIMO = 2 * 1024 * 1024
FILAS_MAXIMAS = 2000

_UNIDADES = {
    "und": Unidad.UNIDAD, "unidad": Unidad.UNIDAD, "unidades": Unidad.UNIDAD, "u": Unidad.UNIDAD,
    "kg": Unidad.KILO, "kilo": Unidad.KILO, "kilos": Unidad.KILO, "kilogramo": Unidad.KILO,
    "lb": Unidad.LIBRA, "libra": Unidad.LIBRA, "libras": Unidad.LIBRA,
}  # fmt: skip
_COLUMNAS = {
    "nombre": "nombre", "producto": "nombre",
    "unidad": "unidad", "unidad de medida": "unidad",
    "precio": "precio", "precio de venta": "precio",
    "cantidad": "cantidad", "cantidad inicial": "cantidad", "existencia": "cantidad",
}  # fmt: skip


@dataclass
class FilaRevisada:
    fila: int
    nombre: str
    unidad: str = ""
    precio: int = 0
    cantidad: str = ""  # texto decimal, para guardarlo en la sesión
    problema: str = ""


@dataclass
class Revision:
    crear: list[FilaRevisada] = field(default_factory=list)
    existentes: list[FilaRevisada] = field(default_factory=list)
    errores: list[FilaRevisada] = field(default_factory=list)

    def a_sesion(self) -> list[dict]:
        return [asdict(f) for f in self.crear]


def _filas_de(archivo) -> list[list[str]]:
    if archivo.size > TAMANO_MAXIMO:
        raise ReglaNegocio("El archivo es muy grande (máximo 2 MB).")
    nombre = archivo.name.lower()
    contenido = archivo.read()
    if nombre.endswith(".xlsx"):
        try:
            libro = load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
        except Exception as error:
            raise ReglaNegocio("No se pudo leer el archivo de Excel.") from error
        hoja = libro.worksheets[0]
        return [
            ["" if c is None else str(c) for c in fila] for fila in hoja.iter_rows(values_only=True)
        ]
    if nombre.endswith(".csv"):
        for codificacion in ("utf-8-sig", "cp1252", "latin-1"):  # latin-1 nunca falla
            try:
                texto = contenido.decode(codificacion)
                break
            except UnicodeDecodeError:
                continue
        # Excel en español guarda los CSV con punto y coma.
        primera = texto.splitlines()[0] if texto else ""
        separador = ";" if primera.count(";") >= primera.count(",") else ","
        return list(csv.reader(io.StringIO(texto), delimiter=separador))
    raise ReglaNegocio("Sube un archivo .xlsx o .csv.")


def revisar(archivo) -> Revision:
    filas = _filas_de(archivo)
    if not filas:
        raise ReglaNegocio("El archivo está vacío.")
    encabezado = [_COLUMNAS.get(normalizar(c)) for c in filas[0]]
    if "nombre" not in encabezado or "unidad" not in encabezado or "precio" not in encabezado:
        raise ReglaNegocio(
            "La primera fila debe tener las columnas nombre, unidad y precio "
            "(descarga el formato de ejemplo)."
        )
    if len(filas) - 1 > FILAS_MAXIMAS:
        raise ReglaNegocio(f"Máximo {FILAS_MAXIMAS} productos por archivo.")

    revision = Revision()
    vistos: set[str] = set()
    for numero, valores in enumerate(filas[1:], start=2):
        datos = {
            col: (valores[i].strip() if i < len(valores) else "")
            for i, col in enumerate(encabezado)
            if col
        }
        if not any(datos.values()):
            continue
        fila = FilaRevisada(fila=numero, nombre=" ".join(datos.get("nombre", "").split()))
        if not fila.nombre:
            fila.problema = "Falta el nombre."
            revision.errores.append(fila)
            continue
        unidad = _UNIDADES.get(normalizar(datos.get("unidad", "")))
        if unidad is None:
            fila.problema = "La unidad no es válida (usa unidad, kg o libra)."
            revision.errores.append(fila)
            continue
        fila.unidad = unidad
        try:
            fila.precio = leer_pesos(datos.get("precio", ""))
            if datos.get("cantidad"):
                cantidad = leer_numero(datos["cantidad"])
                a_base(cantidad, unidad)  # valida unidades enteras
                fila.cantidad = str(cantidad)
        except ValueError as error:
            fila.problema = str(error)
            revision.errores.append(fila)
            continue

        clave = normalizar(fila.nombre)
        if clave in vistos:
            fila.problema = "Está repetido en el archivo."
            revision.existentes.append(fila)
            continue
        if parecidos := catalogo.similares(fila.nombre):
            fila.problema = f"Se parece a «{parecidos[0].nombre}». No se duplica sin avisar."
            revision.existentes.append(fila)
            continue
        vistos.add(clave)
        revision.crear.append(fila)
    return revision


@transaction.atomic
def cargar(por, filas: list[dict]) -> int:
    """Crea los productos revisados. Todo o nada."""
    for datos in filas:
        servicios.dar_de_alta_producto(
            por,
            nombre=datos["nombre"],
            unidad=datos["unidad"],
            precio=datos["precio"],
            cantidad_inicial=Decimal(datos["cantidad"]) if datos["cantidad"] else None,
        )
    return len(filas)


def formato_ejemplo() -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Productos"
    hoja.append(["nombre", "unidad", "precio", "cantidad"])
    hoja.append(["Arroz 500 g", "unidad", 2500, 40])
    hoja.append(["Tomate chonto", "kg", 3000, 12.5])
    hoja.append(["Panela", "libra", 2400, ""])
    for columna, ancho in zip("ABCD", (28, 10, 10, 10), strict=True):
        hoja.column_dimensions[columna].width = ancho
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()
