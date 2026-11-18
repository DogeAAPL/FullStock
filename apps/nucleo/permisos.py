"""Catálogo único de funciones que el dueño puede activar o desactivar por colaborador.

Si cambia un permiso, se cambia aquí y en ningún otro lugar. Las funciones que
no aparecen aquí (usuarios, panel de permisos, configuración, restaurar
respaldos) son exclusivas del dueño y se protegen con
`apps.nucleo.decoradores.solo_dueno`.

Este módulo no importa nada de Django para que los modelos puedan usarlo.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Permiso:
    codigo: str
    nombre: str
    por_defecto: bool


CATALOGO: tuple[Permiso, ...] = (
    Permiso("vender", "Vender", True),
    Permiso("inventario", "Ver y corregir inventario", True),
    Permiso("pedidos", "Hacer y recibir pedidos", True),
    Permiso("proveedores", "Registrar proveedores", True),
    Permiso("crear_productos", "Crear productos", False),
    Permiso("anular_ventas", "Anular o modificar ventas", False),
    Permiso("registrar_fiado", "Registrar ventas fiadas", True),
    Permiso("ver_fiados", "Ver fiados y registrar abonos", False),
    Permiso("cierre_dia", "Cierre del día", False),
    Permiso("estadisticas", "Estadísticas", False),
)

CODIGOS: frozenset[str] = frozenset(p.codigo for p in CATALOGO)
POR_DEFECTO: frozenset[str] = frozenset(p.codigo for p in CATALOGO if p.por_defecto)
APP_LABEL = "nucleo"
