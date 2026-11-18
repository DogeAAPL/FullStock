from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.nucleo.decoradores import solo_autenticado, solo_dueno
from apps.nucleo.errores import ReglaNegocio
from apps.nucleo.models import Configuracion
from apps.nucleo.permisos import CATALOGO, POR_DEFECTO
from apps.nucleo.servicios import actualizar_configuracion

from . import servicios
from .forms import (
    ColaboradorForm,
    ConfiguracionForm,
    EditarColaboradorForm,
    LoginForm,
    PrimerArranqueForm,
    RecuperarForm,
)
from .models import Tema, Usuario

_SESION_CLAVE = "clave_recuperacion_pendiente"


def primer_arranque(request):
    if servicios.hay_usuarios():
        return redirect("usuarios:login")
    form = PrimerArranqueForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            dueno, clave = servicios.crear_dueno(**form.cleaned_data)
        except ReglaNegocio as error:
            form.add_error(None, str(error))
        else:
            login(request, dueno)
            request.session[_SESION_CLAVE] = clave
            return redirect("usuarios:clave")
    return render(request, "usuarios/primer_arranque.html", {"form": form})


def clave_recuperacion(request):
    """Muestra la clave de recuperación una sola vez."""
    clave = request.session.pop(_SESION_CLAVE, None)
    if not clave:
        return redirect("inicio")
    return render(request, "usuarios/clave.html", {"clave": clave})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("inicio")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            usuario = servicios.autenticar(
                form.cleaned_data["usuario"], form.cleaned_data["pin"], request.configuracion
            )
        except ReglaNegocio as error:
            form.add_error(None, str(error))
        else:
            login(request, usuario, backend="django.contrib.auth.backends.ModelBackend")
            destino = request.GET.get("next", "")
            if not url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
                destino = "inicio"
            return redirect(destino)
    return render(request, "usuarios/login.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("usuarios:login")


def recuperar(request):
    form = RecuperarForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            dueno, clave = servicios.recuperar_con_clave(**form.cleaned_data)
        except ReglaNegocio as error:
            form.add_error(None, str(error))
        else:
            login(request, dueno, backend="django.contrib.auth.backends.ModelBackend")
            request.session[_SESION_CLAVE] = clave
            messages.success(
                request, "PIN cambiado. Guarda la clave nueva: la anterior ya no sirve."
            )
            return redirect("usuarios:clave")
    return render(request, "usuarios/recuperar.html", {"form": form})


@solo_dueno
def lista(request):
    usuarios = Usuario.objects.prefetch_related("user_permissions")
    filas = []
    for u in usuarios:
        codigos = (
            {p.codigo for p in CATALOGO}
            if u.es_dueno
            else {perm.codename for perm in u.user_permissions.all()}
        )
        filas.append({"usuario": u, "permisos": codigos})
    return render(request, "usuarios/lista.html", {"filas": filas, "catalogo": CATALOGO})


@solo_dueno
def nuevo(request):
    form = ColaboradorForm(request.POST or None, initial={"permisos": sorted(POR_DEFECTO)})
    if request.method == "POST" and form.is_valid():
        try:
            colaborador = servicios.crear_colaborador(request.user, **form.cleaned_data)
        except ReglaNegocio as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, f"Usuario «{colaborador.usuario}» creado. Dile su PIN.")
            return redirect("usuarios:lista")
    return render(
        request,
        "usuarios/form_usuario.html",
        {"form": form, "titulo": "Nuevo usuario", "boton": "Crear usuario"},
    )


@solo_dueno
def editar(request, pk: int):
    colaborador = get_object_or_404(Usuario, pk=pk, es_dueno=False)
    inicial = {
        "nombre": colaborador.nombre,
        "activo": colaborador.is_active,
        "permisos": sorted(servicios.permisos_de(colaborador)),
    }
    form = EditarColaboradorForm(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        try:
            servicios.actualizar_colaborador(request.user, colaborador, **form.cleaned_data)
        except ReglaNegocio as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, f"Cambios guardados para {colaborador.nombre}.")
            return redirect("usuarios:lista")
    return render(
        request,
        "usuarios/form_usuario.html",
        {
            "form": form,
            "titulo": f"Editar a {colaborador.nombre}",
            "boton": "Guardar cambios",
            "colaborador": colaborador,
        },
    )


@solo_dueno
def configuracion(request):
    form = ConfiguracionForm(request.POST or None, instance=Configuracion.cargar())
    if request.method == "POST" and form.is_valid():
        try:
            actualizar_configuracion(request.user, form.cleaned_data)
        except ReglaNegocio as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, "Configuración guardada.")
            return redirect("usuarios:configuracion")
    return render(request, "usuarios/configuracion.html", {"form": form, "temas": Tema.choices})


@require_POST
@solo_autenticado
def tema(request):
    try:
        servicios.cambiar_tema(request.user, request.POST.get("tema", ""))
    except ReglaNegocio as error:
        messages.error(request, str(error))
    destino = request.POST.get("volver", "")
    if not url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        destino = "inicio"
    return redirect(destino)
