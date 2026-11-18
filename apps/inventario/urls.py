from django.urls import path

from . import views

app_name = "inventario"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("<int:pk>/corregir/", views.corregir, name="corregir"),
    path("nuevo/", views.nuevo_producto, name="nuevo_producto"),
    path("similares/", views.similares, name="similares"),
]
