from django.urls import path

from . import views

app_name = "usuarios"

urlpatterns = [
    path("bienvenida/", views.primer_arranque, name="primer_arranque"),
    path("clave-recuperacion/", views.clave_recuperacion, name="clave"),
    path("entrar/", views.login_view, name="login"),
    path("salir/", views.logout_view, name="logout"),
    path("recuperar/", views.recuperar, name="recuperar"),
    path("usuarios/", views.lista, name="lista"),
    path("usuarios/nuevo/", views.nuevo, name="nuevo"),
    path("usuarios/<int:pk>/", views.editar, name="editar"),
    path("configuracion/", views.configuracion, name="configuracion"),
    path("apariencia/", views.tema, name="tema"),
]
