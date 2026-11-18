from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class ItemMenu:
    nombre: str
    url_name: str
    icono: str
    prefijos: tuple[str, ...]  # vistas que marcan este ítem como activo

    def activo(self, vista: str) -> bool:
        return any(vista.startswith(p) for p in self.prefijos)


# Menú lateral. Cada ítem general se muestra solo si el usuario tiene el permiso.
_MENU_GENERAL = (
    ("vender", ItemMenu("Vender", "ventas:vender", "carrito", ("ventas:",))),
    ("inventario", ItemMenu("Inventario", "inventario:lista", "caja", ("inventario:",))),
    (
        "pedidos",
        ItemMenu(
            "Pedidos",
            "pedidos:pendientes",
            "camion",
            ("pedidos:pendientes", "pedidos:nuevo", "pedidos:recibir", "pedidos:historial"),
        ),
    ),
    (
        "proveedores",
        ItemMenu("Proveedores", "pedidos:proveedores", "tienda", ("pedidos:proveedores",)),
    ),
)
# Funciones de gestión: el dueño las tiene todas y puede delegarlas.
_MENU_GESTION = (
    ("ver_fiados", ItemMenu("Fiados", "fiados:lista", "billete", ("fiados:",))),
    (
        "cierre_dia",
        ItemMenu("Cierre del día", "reportes:cierre", "calculadora", ("reportes:cierre",)),
    ),
    (
        "estadisticas",
        ItemMenu("Estadísticas", "reportes:estadisticas", "grafica", ("reportes:estadisticas",)),
    ),
)
_MENU_DUENO = (
    ItemMenu(
        "Usuarios",
        "usuarios:lista",
        "persona",
        ("usuarios:lista", "usuarios:nuevo", "usuarios:editar"),
    ),
    ItemMenu("Configuración", "usuarios:configuracion", "ajustes", ("usuarios:configuracion",)),
)


def navegacion(request) -> dict:
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return {"tienda_nombre": settings.TIENDA_NOMBRE, "modo_demo": settings.DEMO}
    match = getattr(request, "resolver_match", None)
    vista = match.view_name if match else ""

    def items(lista):
        return [{"item": i, "activo": i.activo(vista)} for i in lista]

    return {
        "menu_general": items(i for permiso, i in _MENU_GENERAL if usuario.tiene_permiso(permiso)),
        "menu_gestion": items(i for permiso, i in _MENU_GESTION if usuario.tiene_permiso(permiso)),
        "menu_dueno": items(_MENU_DUENO) if usuario.es_dueno else [],
        "minutos_inactividad": request.configuracion.minutos_inactividad,
        "tienda_nombre": settings.TIENDA_NOMBRE,
        "modo_demo": settings.DEMO,
    }
