"""Venta en curso, guardada en la sesión del servidor.

Así no se pierde si el vendedor cambia de pantalla y vuelve.
"""

import uuid
from dataclasses import dataclass

from apps.catalogo.models import Producto
from apps.nucleo.dinero import subtotal

from .servicios import LineaNueva

_CLAVE = "carrito"


@dataclass
class LineaCarrito:
    indice: int
    producto: Producto
    cantidad: int
    precio: int

    @property
    def subtotal(self) -> int:
        return subtotal(self.precio, self.cantidad, self.producto.unidad)


class Carrito:
    def __init__(self, session):
        self._session = session
        datos = session.get(_CLAVE) or {}
        self._lineas: list[dict] = datos.get("lineas", [])
        self.token: str = datos.get("token") or str(uuid.uuid4())
        self.corrige_a: int | None = datos.get("corrige_a")
        self.cliente_id: int | None = datos.get("cliente_id")

    # --- Cambios -----------------------------------------------------------

    def agregar(self, producto_id: int, cantidad: int, precio: int) -> None:
        for linea in self._lineas:
            if linea["producto_id"] == producto_id and linea["precio"] == precio:
                linea["cantidad"] += cantidad
                break
        else:
            self._lineas.append(
                {"producto_id": producto_id, "cantidad": cantidad, "precio": precio}
            )
        self._guardar()

    def quitar(self, indice: int) -> None:
        if 0 <= indice < len(self._lineas):
            del self._lineas[indice]
            self._guardar()

    def vaciar(self) -> None:
        self._session.pop(_CLAVE, None)
        self._lineas = []
        self.token = str(uuid.uuid4())
        self.corrige_a = None
        self.cliente_id = None

    def cargar_para_corregir(self, venta) -> None:
        self._lineas = [
            {"producto_id": li.producto_id, "cantidad": li.cantidad, "precio": li.precio}
            for li in venta.lineas.all()
        ]
        self.token = str(uuid.uuid4())
        self.corrige_a = venta.pk
        self.cliente_id = venta.cliente_id if venta.es_fiado else None
        self._guardar()

    # --- Lectura -----------------------------------------------------------

    def __len__(self) -> int:
        return len(self._lineas)

    def lineas(self) -> list[LineaCarrito]:
        productos = Producto.objects.in_bulk({li["producto_id"] for li in self._lineas})
        return [
            LineaCarrito(i, productos[li["producto_id"]], li["cantidad"], li["precio"])
            for i, li in enumerate(self._lineas)
            if li["producto_id"] in productos
        ]

    def lineas_nuevas(self) -> list[LineaNueva]:
        return [LineaNueva(li["producto_id"], li["cantidad"], li["precio"]) for li in self._lineas]

    @property
    def token_uuid(self) -> uuid.UUID:
        return uuid.UUID(self.token)

    def _guardar(self) -> None:
        self._session[_CLAVE] = {
            "lineas": self._lineas,
            "token": self.token,
            "corrige_a": self.corrige_a,
            "cliente_id": self.cliente_id,
        }
