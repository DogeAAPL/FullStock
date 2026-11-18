from django.urls import path

from . import views

app_name = "fiados"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nuevo/", views.nuevo_cliente, name="nuevo_cliente"),
    path("<int:pk>/", views.cliente, name="cliente"),
    path("<int:pk>/abonar/", views.abonar, name="abonar"),
    path("<int:pk>/editar/", views.editar_cliente, name="editar_cliente"),
]
