from django import forms
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.nucleo.decoradores import requiere_permiso
from apps.nucleo.dinero import leer_pesos
from apps.nucleo.errores import ReglaNegocio

from . import servicios
from .models import Cliente


class ClienteForm(forms.Form):
    nombre = forms.CharField(label="Nombre", max_length=120)
    telefono = forms.CharField(label="Teléfono (opcional)", max_length=30, required=False)


@requiere_permiso("ver_fiados")
def lista(request):
    texto = request.GET.get("q", "")
    todos = request.GET.get("todos") == "1"
    clientes = servicios.clientes_para_cobrar(texto, solo_con_deuda=not todos)
    contexto = {
        "clientes": clientes,
        "q": texto,
        "todos": todos,
        "total": servicios.total_por_cobrar(),
        "limite": request.configuracion.limite_deuda,
        "form": ClienteForm(),
    }
    if request.headers.get("HX-Request"):
        return render(request, "fiados/_tabla.html", contexto)
    return render(request, "fiados/lista.html", contexto)


@requiere_permiso("ver_fiados")
@require_POST
def nuevo_cliente(request):
    form = ClienteForm(request.POST)
    if form.is_valid():
        try:
            cliente = servicios.crear_cliente(request.user, **form.cleaned_data)
        except ReglaNegocio as error:
            messages.error(request, str(error))
        else:
            messages.success(request, f"Cliente «{cliente.nombre}» creado.")
            return redirect("fiados:cliente", pk=cliente.pk)
    else:
        messages.error(request, "Escribe el nombre del cliente.")
    return redirect("fiados:lista")


@requiere_permiso("ver_fiados")
def cliente(request, pk: int):
    cliente = get_object_or_404(Cliente, pk=pk)
    pagina = Paginator(servicios.movimientos_de(cliente.pk), 30).get_page(request.GET.get("pagina"))
    limite = request.configuracion.limite_deuda
    return render(
        request,
        "fiados/cliente.html",
        {
            "cliente": cliente,
            "pagina": pagina,
            "form": ClienteForm(initial={"nombre": cliente.nombre, "telefono": cliente.telefono}),
            "limite": limite,
            "sobre_limite": servicios.supera_limite(cliente, 0, limite),
        },
    )


@requiere_permiso("ver_fiados")
@require_POST
def abonar(request, pk: int):
    cliente = get_object_or_404(Cliente, pk=pk)
    try:
        monto = leer_pesos(request.POST.get("monto", ""))
        servicios.registrar_abono(request.user, cliente_id=cliente.pk, monto=monto)
    except (ValueError, ReglaNegocio) as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"Abono registrado para {cliente.nombre}.")
    return redirect("fiados:cliente", pk=cliente.pk)


@requiere_permiso("ver_fiados")
@require_POST
def editar_cliente(request, pk: int):
    cliente = get_object_or_404(Cliente, pk=pk)
    form = ClienteForm(request.POST)
    if form.is_valid():
        try:
            servicios.actualizar_cliente(request.user, cliente, **form.cleaned_data)
        except ReglaNegocio as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Datos del cliente guardados.")
    return redirect("fiados:cliente", pk=cliente.pk)
