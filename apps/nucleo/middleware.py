import time

from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import SimpleLazyObject

from .models import Configuracion

# Para no escribir la sesión en cada clic, la actividad se anota cada 30 s.
_REFRESCO_ACTIVIDAD = 30


def _es_estatico(request) -> bool:
    return request.path.startswith("/static/")


class ConfiguracionMiddleware:
    """Expone `request.configuracion`, leída como máximo una vez por petición."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.configuracion = SimpleLazyObject(Configuracion.cargar)
        return self.get_response(request)


class PrimerArranqueMiddleware:
    """Si todavía no hay usuarios, todo lleva a crear el dueño."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            not _es_estatico(request)
            and not request.user.is_authenticated
            and request.path != reverse("usuarios:primer_arranque")
            and not get_user_model().objects.exists()
        ):
            return redirect("usuarios:primer_arranque")
        return self.get_response(request)


class InactividadMiddleware:
    """Cierra la sesión tras los minutos de inactividad que fijó el dueño.

    Las tres personas comparten el computador: una sesión olvidada abierta haría
    que las ventas queden a nombre de quien no las hizo.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not _es_estatico(request):
            ahora = time.time()
            ultima = request.session.get("ultima_actividad")
            limite = request.configuracion.minutos_inactividad * 60
            if ultima is not None and ahora - ultima > limite:
                logout(request)
                messages.info(request, "La sesión se cerró por inactividad.")
                if request.headers.get("HX-Request"):
                    # HTMX no sigue redirecciones de página completa; se le indica por cabecera.
                    respuesta = HttpResponse(status=204)
                    respuesta["HX-Redirect"] = reverse("usuarios:login")
                    return respuesta
                return redirect_to_login(request.get_full_path())
            if ultima is None or ahora - ultima > _REFRESCO_ACTIVIDAD:
                request.session["ultima_actividad"] = ahora
        return self.get_response(request)
