from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


@login_required
def inicio(request):
    """Lleva a la primera pantalla que el usuario puede usar."""
    usuario = request.user
    if usuario.tiene_permiso("vender"):
        return redirect("ventas:vender")
    if usuario.tiene_permiso("inventario"):
        return redirect("inventario:lista")
    if usuario.es_dueno:
        return redirect("usuarios:lista")
    raise PermissionDenied
