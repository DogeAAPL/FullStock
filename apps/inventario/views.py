from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Subquery
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.catalogo import servicios as catalogo
from apps.catalogo.models import Producto
from apps.nucleo.cantidades import a_base
from apps.nucleo.decoradores import requiere_permiso
from apps.nucleo.dinero import leer_pesos
from apps.nucleo.errores import ReglaNegocio
from apps.nucleo.numeros import leer_numero
from apps.pedidos.models import EstadoPedido, Pedido

from . import carga, servicios
from .forms import CorregirForm, NuevoProductoForm
from .models import MotivoAjuste, MovimientoInventario, TipoMovimiento

_POR_PAGINA = 50


def _productos_con_ultimo_conteo(texto: str):
    # Subconsulta por producto: usa el índice (producto, fecha) en vez de agrupar
    # todos los movimientos de la historia.
    ultimo_conteo = (
        MovimientoInventario.objects.filter(
            producto=OuterRef("pk"), tipo=TipoMovimiento.AJUSTE, motivo=MotivoAjuste.CONTEO
        )
        .order_by("-fecha")
        .values("fecha")[:1]
    )
    pedido_pendiente = Pedido.objects.filter(producto=OuterRef("pk"), estado=EstadoPedido.PENDIENTE)
    return catalogo.buscar(texto, limite=None).annotate(
        ultimo_conteo=Subquery(ultimo_conteo), pedido_pendiente=Exists(pedido_pendiente)
    )


@requiere_permiso("inventario")
def lista(request):
    texto = request.GET.get("q", "")
    pagina = Paginator(_productos_con_ultimo_conteo(texto), _POR_PAGINA).get_page(
        request.GET.get("pagina")
    )
    contexto = {
        "pagina": pagina,
        "q": texto,
        "puede_crear": request.user.tiene_permiso("crear_productos"),
    }
    plantilla = (
        "inventario/_tabla.html" if request.headers.get("HX-Request") else "inventario/lista.html"
    )
    return render(request, plantilla, contexto)


@requiere_permiso("inventario")
def corregir(request, pk: int):
    producto = get_object_or_404(Producto, pk=pk, activo=True)
    form = CorregirForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            nueva = a_base(leer_numero(form.cleaned_data["nueva_cantidad"]), producto.unidad)
            servicios.corregir_existencia(
                request.user,
                producto_id=producto.pk,
                nueva_cantidad=nueva,
                motivo=form.cleaned_data["motivo"],
            )
        except (ValueError, ReglaNegocio) as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, f"Inventario de «{producto.nombre}» corregido.")
            respuesta = HttpResponse(status=204)
            respuesta["HX-Redirect"] = reverse("inventario:lista")
            return respuesta
    return render(request, "inventario/_corregir.html", {"form": form, "producto": producto})


@requiere_permiso("crear_productos")
def nuevo_producto(request):
    form = NuevoProductoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data
        try:
            cantidad = datos["cantidad_inicial"].strip()
            producto = servicios.dar_de_alta_producto(
                request.user,
                nombre=datos["nombre"],
                unidad=datos["unidad"],
                precio=leer_pesos(datos["precio"]),
                cantidad_inicial=leer_numero(cantidad) if cantidad else None,
            )
        except (ValueError, ReglaNegocio) as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, f"Producto «{producto.nombre}» creado.")
            return redirect("inventario:lista")
    return render(request, "inventario/nuevo_producto.html", {"form": form})


@requiere_permiso("crear_productos")
@require_GET
def similares(request):
    return render(
        request,
        "inventario/_similares.html",
        {"similares": catalogo.similares(request.GET.get("nombre", ""))[:3]},
    )


_SESION_CARGA = "carga_productos"


@requiere_permiso("crear_productos")
def cargar(request):
    """Carga desde Excel/CSV en dos pasos: revisar el archivo y luego confirmar."""
    contexto: dict = {}
    if request.method == "POST" and request.POST.get("confirmar"):
        filas = request.session.pop(_SESION_CARGA, [])
        if not filas:
            messages.error(
                request, "No hay productos revisados para cargar. Sube el archivo otra vez."
            )
            return redirect("inventario:cargar")
        try:
            creados = carga.cargar(request.user, filas)
        except ReglaNegocio as error:
            messages.error(request, f"No se cargó nada: {error}")
            return redirect("inventario:cargar")
        plural = "s" if creados != 1 else ""
        messages.success(request, f"{creados} producto{plural} cargado{plural}.")
        return redirect("inventario:lista")
    if request.method == "POST":
        archivo = request.FILES.get("archivo")
        if archivo is None:
            contexto["error"] = "Elige un archivo."
        else:
            try:
                revision = carga.revisar(archivo)
            except ReglaNegocio as error:
                contexto["error"] = str(error)
            else:
                request.session[_SESION_CARGA] = revision.a_sesion()
                contexto["revision"] = revision
                contexto["archivo"] = archivo.name
    return render(request, "inventario/cargar.html", contexto)


@requiere_permiso("crear_productos")
@require_GET
def formato_ejemplo(request):
    respuesta = HttpResponse(
        carga.formato_ejemplo(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    respuesta["Content-Disposition"] = 'attachment; filename="formato_productos.xlsx"'
    return respuesta
