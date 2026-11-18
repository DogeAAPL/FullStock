from difflib import SequenceMatcher

from django.db.models import QuerySet

from apps.nucleo import servicios as nucleo
from apps.nucleo.cantidades import Unidad
from apps.nucleo.errores import ReglaNegocio
from apps.nucleo.texto import normalizar

from .models import Producto

_SIMILITUD_MINIMA = 0.8


def buscar(texto: str, limite: int = 50) -> QuerySet[Producto]:
    consulta = Producto.objects.filter(activo=True)
    if texto := normalizar(texto or ""):
        consulta = consulta.filter(nombre_normalizado__contains=texto)
    return consulta.order_by("nombre")[:limite]


def similares(nombre: str, excluir_id: int | None = None) -> list[Producto]:
    """Productos con nombre parecido, para avisar antes de crear un duplicado.

    No bloquea: puede haber «Tomate chonto» y «Tomate de árbol».
    """
    buscado = normalizar(nombre or "")
    if len(buscado) < 3:
        return []
    candidatos = Producto.objects.filter(activo=True).only("id", "nombre", "nombre_normalizado")
    if excluir_id:
        candidatos = candidatos.exclude(pk=excluir_id)
    return [
        p
        for p in candidatos
        if buscado in p.nombre_normalizado
        or p.nombre_normalizado in buscado
        or SequenceMatcher(None, buscado, p.nombre_normalizado).ratio() >= _SIMILITUD_MINIMA
    ]


def crear_producto(por, nombre: str, unidad: str, precio: int) -> Producto:
    """Crea el producto sin existencia. Para crearlo con cantidad inicial usa
    `inventario.servicios.dar_de_alta_producto`."""
    if not por.tiene_permiso("crear_productos"):
        raise ReglaNegocio("No tienes permiso para crear productos.")
    nombre = " ".join((nombre or "").split())
    if not nombre:
        raise ReglaNegocio("Escribe el nombre del producto.")
    if unidad not in Unidad.values:
        raise ReglaNegocio("La unidad no es válida (usa unidad, kg o libra).")
    if precio < 0:
        raise ReglaNegocio("El precio no puede ser negativo.")
    producto = Producto.objects.create(nombre=nombre, unidad=unidad, precio=precio, creado_por=por)
    nucleo.registrar(por, "catalogo.crear_producto", producto=producto.pk, nombre=nombre)
    return producto
