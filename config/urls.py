from django.urls import include, path

from apps.nucleo.views import inicio

urlpatterns = [
    path("", inicio, name="inicio"),
    path("", include("apps.usuarios.urls")),
    path("inventario/", include("apps.inventario.urls")),
    path("vender/", include("apps.ventas.urls")),
]
