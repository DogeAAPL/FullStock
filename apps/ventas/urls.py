from django.urls import path

from . import views

app_name = "ventas"

urlpatterns = [
    path("", views.vender, name="vender"),
    path("productos/", views.buscar_productos, name="buscar_productos"),
    path("productos/<int:pk>/", views.seleccionar_producto, name="seleccionar_producto"),
    path("agregar/", views.agregar, name="agregar"),
    path("quitar/<int:indice>/", views.quitar, name="quitar"),
    path("vaciar/", views.vaciar, name="vaciar"),
    path("clientes/", views.buscar_clientes, name="buscar_clientes"),
    path("guardar/", views.guardar, name="guardar"),
    path("hoy/", views.ventas_hoy, name="hoy"),
    path("<int:pk>/anular/", views.anular, name="anular"),
    path("<int:pk>/corregir/", views.corregir, name="corregir"),
]
