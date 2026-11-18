from datetime import timedelta

from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.catalogo import servicios as catalogo
from apps.catalogo.models import Producto
from apps.fiados import servicios as fiados
from apps.fiados.models import Cliente
from apps.nucleo.cantidades import a_base
from apps.nucleo.decoradores import requiere_permiso
from apps.nucleo.dinero import formatear_pesos, leer_pesos
from apps.nucleo.errores import ReglaNegocio
from apps.nucleo.fechas import hoy
from apps.nucleo.numeros import leer_numero

from . import servicios
from .carrito import Carrito
from .models import LineaVenta, Venta

_ATAJOS = 4


def _atajos() -> list[Producto]:
    """Los productos más vendidos de los últimos 30 días, para agregarlos con un clic."""
    desde = timezone.now() - timedelta(days=30)
    ids = list(
        LineaVenta.objects.filter(venta__fecha__gte=desde, venta__anulada=False)
        .values("producto")
        .annotate(n=Count("id"))
        .order_by("-n")
        .values_list("producto", flat=True)[:_ATAJOS]
    )
    productos = Producto.objects.filter(activo=True)
    if ids:
        encontrados = productos.in_bulk(ids)
        return [encontrados[i] for i in ids if i in encontrados]
    return list(productos[:_ATAJOS])


def _contexto(request, carrito: Carrito, **extra) -> dict:
    lineas = carrito.lineas()
    contexto = {
        "atajos": _atajos(),
        "lineas": lineas,
        "total": sum(li.subtotal for li in lineas),
        "carrito": carrito,
        "puede_fiar": request.user.tiene_permiso("registrar_fiado"),
        "venta_corregida": (
            Venta.objects.filter(pk=carrito.corrige_a).first() if carrito.corrige_a else None
        ),
        "cliente_actual": (
            Cliente.objects.filter(pk=carrito.cliente_id).first() if carrito.cliente_id else None
        ),
    }
    contexto.update(extra)
    return contexto


def _cuerpo(request, carrito: Carrito, **extra) -> HttpResponse:
    return render(request, "ventas/_cuerpo.html", _contexto(request, carrito, **extra))


@requiere_permiso("vender")
def vender(request):
    carrito = Carrito(request.session)
    contexto = _contexto(request, carrito, resumen=servicios.resumen_del_dia(hoy()), hoy=hoy())
    return render(request, "ventas/vender.html", contexto)


@requiere_permiso("vender")
@require_GET
def buscar_productos(request):
    texto = request.GET.get("q", "")
    productos = catalogo.buscar(texto, limite=8) if texto.strip() else []
    return render(request, "ventas/_resultados.html", {"productos": productos})


@requiere_permiso("vender")
@require_GET
def seleccionar_producto(request, pk: int):
    """Muestra el formulario de agregar con el producto elegido (pk=0: sin producto)."""
    producto = get_object_or_404(Producto, pk=pk, activo=True) if pk else None
    return render(request, "ventas/_agregar.html", {"producto": producto})


@requiere_permiso("vender")
@require_POST
def agregar(request):
    carrito = Carrito(request.session)
    producto = Producto.objects.filter(pk=request.POST.get("producto_id"), activo=True).first()
    try:
        if producto is None:
            raise ReglaNegocio("Elige un producto.")
        cantidad = a_base(leer_numero(request.POST.get("cantidad", "")), producto.unidad)
        if cantidad <= 0:
            raise ReglaNegocio("La cantidad debe ser mayor que cero.")
        precio = leer_pesos(request.POST.get("precio", ""))
    except (ValueError, ReglaNegocio) as error:
        return _cuerpo(request, carrito, error_agregar=str(error), producto=producto)
    carrito.agregar(producto.pk, cantidad, precio)
    return _cuerpo(request, carrito)


@requiere_permiso("vender")
@require_POST
def quitar(request, indice: int):
    carrito = Carrito(request.session)
    carrito.quitar(indice)
    return _cuerpo(request, carrito)


@requiere_permiso("vender")
@require_POST
def vaciar(request):
    carrito = Carrito(request.session)
    carrito.vaciar()
    return _cuerpo(request, carrito)


@requiere_permiso("registrar_fiado")
@require_GET
def buscar_clientes(request):
    clientes = fiados.buscar_clientes(request.GET.get("q", ""), limite=6)
    limite = request.configuracion.limite_deuda
    return render(request, "ventas/_clientes.html", {"clientes": clientes, "limite": limite})


@requiere_permiso("vender")
@require_POST
def guardar(request):
    carrito = Carrito(request.session)
    try:
        cliente_id = _cliente_de_la_venta(request)
        if carrito.corrige_a:
            venta = servicios.corregir_venta(
                por=request.user,
                venta_id=carrito.corrige_a,
                lineas=carrito.lineas_nuevas(),
                token=carrito.token_uuid,
                cliente_id=cliente_id,
            )
        else:
            venta = servicios.registrar_venta(
                usuario=request.user,
                lineas=carrito.lineas_nuevas(),
                token=carrito.token_uuid,
                cliente_id=cliente_id,
            )
    except ReglaNegocio as error:
        return _cuerpo(request, carrito, error_guardar=str(error))
    carrito.vaciar()
    messages.success(request, f"Venta guardada por {formatear_pesos(venta.total)}.")
    respuesta = HttpResponse(status=204)
    respuesta["HX-Redirect"] = reverse("ventas:vender")
    return respuesta


def _cliente_de_la_venta(request) -> int | None:
    if request.POST.get("es_fiado") != "on":
        return None
    if cliente_id := request.POST.get("cliente_id"):
        return get_object_or_404(Cliente, pk=cliente_id).pk
    if nombre := request.POST.get("cliente_nuevo", "").strip():
        return fiados.crear_cliente(request.user, nombre).pk
    raise ReglaNegocio("Elige o crea el cliente del fiado.")


@requiere_permiso("vender")
def ventas_hoy(request):
    dia = hoy()
    return render(
        request,
        "ventas/ventas_hoy.html",
        {
            "ventas": servicios.ventas_del_dia(dia),
            "resumen": servicios.resumen_del_dia(dia),
            "puede_anular": request.user.tiene_permiso("anular_ventas"),
        },
    )


@requiere_permiso("anular_ventas")
def anular(request, pk: int):
    venta = get_object_or_404(Venta.objects.select_related("usuario"), pk=pk, anulada=False)
    if request.method == "POST":
        try:
            servicios.anular_venta(por=request.user, venta_id=pk, motivo=request.POST.get("motivo"))
        except ReglaNegocio as error:
            return render(request, "ventas/_anular.html", {"venta": venta, "error": str(error)})
        messages.success(request, f"Venta de las {timezone.localtime(venta.fecha):%H:%M} anulada.")
        respuesta = HttpResponse(status=204)
        respuesta["HX-Redirect"] = reverse("ventas:hoy")
        return respuesta
    return render(request, "ventas/_anular.html", {"venta": venta})


@requiere_permiso("anular_ventas")
@require_POST
def corregir(request, pk: int):
    venta = get_object_or_404(Venta.objects.prefetch_related("lineas"), pk=pk, anulada=False)
    Carrito(request.session).cargar_para_corregir(venta)
    messages.info(request, "Cambia lo que necesites y guarda: la venta original quedará anulada.")
    return redirect("ventas:vender")
