from django.urls import path

from . import views

app_name = "pedidos"

urlpatterns = [
    path("", views.pendientes, name="pendientes"),
    path("historial/", views.historial, name="historial"),
    path("nuevo/", views.nuevo, name="nuevo"),
    path("productos/", views.buscar_productos, name="buscar_productos"),
    path("productos/<int:pk>/", views.elegir_producto, name="elegir_producto"),
    path("resumen/", views.resumen, name="resumen"),
    path("<int:pk>/recibir/", views.recibir, name="recibir"),
    path("<int:pk>/cancelar/", views.cancelar, name="cancelar"),
    path("proveedores/", views.proveedores, name="proveedores"),
]
