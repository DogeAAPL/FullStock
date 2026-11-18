import contextlib

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.catalogo import servicios as catalogo
from apps.catalogo.models import Producto
from apps.nucleo.cantidades import a_base, desde_base
from apps.nucleo.decoradores import requiere_permiso
from apps.nucleo.dinero import leer_pesos, subtotal
from apps.nucleo.errores import ReglaNegocio
from apps.nucleo.fechas import hoy
from apps.nucleo.numeros import formatear_decimal, leer_numero
from apps.nucleo.texto import normalizar

from . import servicios
from .forms import PedidoForm, ProveedorForm, RecibirForm
from .models import EstadoPedido, Pedido, Proveedor

# --- Pedidos ----------------------------------------------------------------


@requiere_permiso("pedidos")
def pendientes(request):
    lista = list(servicios.pendientes())
    dia = hoy()
    for pedido in lista:
        pedido.dias_espera = (dia - pedido.fecha_pedido).days
    return render(request, "pedidos/pendientes.html", {"pedidos": lista})


@requiere_permiso("pedidos")
def historial(request):
    return render(request, "pedidos/historial.html", {"pedidos": servicios.historial()})


def _producto_elegido(producto_id) -> Producto | None:
    if not producto_id:
        return None
    return Producto.objects.filter(pk=producto_id, activo=True).first()


def _contexto_pedido(form, producto) -> dict:
    datos = form.data if form.is_bound else {}
    total = None
    try:
        if producto and datos.get("cantidad") and datos.get("costo_unitario"):
            total = subtotal(
                leer_pesos(datos["costo_unitario"]),
                a_base(leer_numero(datos["cantidad"]), producto.unidad),
                producto.unidad,
            )
    except ValueError:
        total = None
    return {
        "form": form,
        "producto": producto,
        "ya_pedidos": list(servicios.pendientes_de(producto.pk)) if producto else [],
        "total": total,
    }


@requiere_permiso("pedidos")
def nuevo(request):
    proveedores = Proveedor.objects.order_by("nombre")
    datos = request.POST if request.method == "POST" else None
    form = PedidoForm(datos, proveedores=proveedores, initial={"fecha_pedido": hoy()})
    producto = _producto_elegido(request.POST.get("producto_id") or request.GET.get("producto"))
    if request.method == "POST" and form.is_valid():
        try:
            if producto is None:
                raise ReglaNegocio("Elige un producto.")
            servicios.crear_pedido(
                request.user,
                producto_id=producto.pk,
                proveedor_id=form.cleaned_data["proveedor_id"],
                cantidad=a_base(leer_numero(form.cleaned_data["cantidad"]), producto.unidad),
                costo_unitario=leer_pesos(form.cleaned_data["costo_unitario"]),
                fecha_pedido=form.cleaned_data["fecha_pedido"],
            )
        except (ValueError, ReglaNegocio) as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, f"Pedido de «{producto.nombre}» guardado.")
            return redirect("pedidos:pendientes")
    contexto = _contexto_pedido(form, producto)
    contexto["sin_proveedores"] = not proveedores.exists()
    return render(request, "pedidos/nuevo.html", contexto)


@requiere_permiso("pedidos")
@require_GET
def buscar_productos(request):
    texto = request.GET.get("q", "")
    productos = catalogo.buscar(texto, limite=8) if texto.strip() else []
    return render(request, "pedidos/_resultados.html", {"productos": productos})


@requiere_permiso("pedidos")
@require_GET
def elegir_producto(request, pk: int):
    """Fragmento con el producto elegido y el aviso si ya hay pedidos pendientes."""
    producto = get_object_or_404(Producto, pk=pk, activo=True) if pk else None
    return render(
        request,
        "pedidos/_producto.html",
        {"producto": producto, "ya_pedidos": servicios.pendientes_de(pk) if producto else []},
    )


@requiere_permiso("pedidos")
@require_GET
def resumen(request):
    producto = _producto_elegido(request.GET.get("producto_id"))
    form = PedidoForm(request.GET, proveedores=Proveedor.objects.all())
    contexto = _contexto_pedido(form, producto)
    contexto["proveedor"] = Proveedor.objects.filter(
        pk=request.GET.get("proveedor_id") or 0
    ).first()
    return render(request, "pedidos/_resumen.html", contexto)


@requiere_permiso("pedidos")
def recibir(request, pk: int):
    pedido = get_object_or_404(
        Pedido.objects.select_related("producto", "proveedor"), pk=pk, estado=EstadoPedido.PENDIENTE
    )
    unidad = pedido.producto.unidad
    inicial = {
        "cantidad_recibida": formatear_decimal(desde_base(pedido.cantidad, unidad)),
        "costo_unitario": formatear_decimal(pedido.costo_unitario),
        "fecha_llegada": hoy(),
    }
    form = RecibirForm(request.POST or None, initial=inicial)
    llegada = None
    if form.is_bound:
        try:
            llegada = a_base(leer_numero(form.data.get("cantidad_recibida", "")), unidad)
            costo = leer_pesos(form.data.get("costo_unitario", ""))
        except ValueError as error:
            form.add_error(None, str(error))
            llegada = None
    # "revisar" solo recalcula el resumen; no confirma la llegada.
    confirmar = request.method == "POST" and "revisar" not in request.POST
    if confirmar and form.is_valid() and llegada is not None:
        try:
            servicios.recibir_pedido(
                request.user,
                pedido_id=pedido.pk,
                cantidad_recibida=llegada,
                costo_unitario=costo,
                fecha_llegada=form.cleaned_data["fecha_llegada"],
            )
        except ReglaNegocio as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, f"Llegada de «{pedido.producto.nombre}» registrada.")
            return redirect("pedidos:pendientes")
    cantidad_vista = llegada if llegada is not None else pedido.cantidad
    costo_vista = pedido.costo_unitario
    if form.is_bound:
        with contextlib.suppress(ValueError):
            costo_vista = leer_pesos(form.data.get("costo_unitario", ""))
    return render(
        request,
        "pedidos/recibir.html",
        {
            "form": form,
            "pedido": pedido,
            "llegada": cantidad_vista,
            "faltante": max(pedido.cantidad - cantidad_vista, 0),
            "gasto": subtotal(costo_vista, cantidad_vista, unidad),
            "costo_vista": costo_vista,
        },
    )


@requiere_permiso("pedidos")
def cancelar(request, pk: int):
    pedido = get_object_or_404(
        Pedido.objects.select_related("producto", "proveedor"), pk=pk, estado=EstadoPedido.PENDIENTE
    )
    if request.method == "POST":
        try:
            servicios.cancelar_pedido(request.user, pedido_id=pk)
        except ReglaNegocio as error:
            return render(
                request, "pedidos/_cancelar.html", {"pedido": pedido, "error": str(error)}
            )
        messages.success(request, f"Pedido de «{pedido.producto.nombre}» cancelado.")
        respuesta = HttpResponse(status=204)
        respuesta["HX-Redirect"] = reverse("pedidos:pendientes")
        return respuesta
    return render(request, "pedidos/_cancelar.html", {"pedido": pedido})


# --- Proveedores ------------------------------------------------------------


@requiere_permiso("proveedores")
def proveedores(request):
    form = ProveedorForm(request.POST or None)
    repetidos = []
    if request.method == "POST" and form.is_valid():
        repetidos = servicios.proveedores_con_mismo_nombre(form.cleaned_data["nombre"])
        if not repetidos or request.POST.get("confirmar") == "1":
            try:
                proveedor = servicios.crear_proveedor(request.user, **form.cleaned_data)
            except ReglaNegocio as error:
                form.add_error(None, str(error))
            else:
                messages.success(request, f"Proveedor «{proveedor.nombre}» guardado.")
                return redirect("pedidos:proveedores")
    texto = request.GET.get("q", "")
    lista = servicios.proveedores_con_pendientes()
    if texto.strip():
        lista = lista.filter(nombre_normalizado__contains=normalizar(texto))
    contexto = {"form": form, "proveedores": lista, "q": texto, "repetidos": repetidos}
    if request.headers.get("HX-Request") and request.method == "GET":
        return render(request, "pedidos/_tabla_proveedores.html", contexto)
    return render(request, "pedidos/proveedores.html", contexto)
