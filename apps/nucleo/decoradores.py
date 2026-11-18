"""Protección de vistas en el servidor. Ocultar un botón no protege nada."""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .permisos import CODIGOS


def requiere_permiso(codigo: str):
    """Exige uno de los permisos delegables del catálogo."""
    if codigo not in CODIGOS:
        raise ValueError(f"Permiso desconocido: {codigo}")

    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not request.user.tiene_permiso(codigo):
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        envoltura.permiso_requerido = codigo
        return envoltura

    return decorador


def solo_dueno(vista):
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.es_dueno:
            raise PermissionDenied
        return vista(request, *args, **kwargs)

    envoltura.permiso_requerido = "solo_dueno"
    return envoltura


def solo_autenticado(vista):
    """Para preferencias personales que cualquier usuario puede cambiar."""

    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        return vista(request, *args, **kwargs)

    envoltura.permiso_requerido = "autenticado"
    return envoltura
