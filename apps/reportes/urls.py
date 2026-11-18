from django.urls import path

from . import views

app_name = "reportes"

urlpatterns = [
    path("cierre/", views.cierre, name="cierre"),
    path("cierre/cerrar/", views.cerrar, name="cerrar"),
    path("estadisticas/", views.estadisticas, name="estadisticas"),
]
