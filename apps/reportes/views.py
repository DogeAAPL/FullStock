from datetime import date

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.nucleo.decoradores import requiere_permiso
from apps.nucleo.dinero import leer_pesos
from apps.nucleo.errores import ReglaNegocio
from apps.nucleo.fechas import hoy

from . import servicios
from .models import CierreDia

_PERIODOS = (7, 30, 90)


def _fecha(texto: str | None) -> date:
    try:
        dia = date.fromisoformat(texto) if texto else hoy()
    except ValueError:
        dia = hoy()
    return min(dia, hoy())


@requiere_permiso("cierre_dia")
def cierre(request):
    dia = _fecha(request.GET.get("fecha"))
    return render(
        request,
        "reportes/cierre.html",
        {
            "resumen": servicios.calcular_dia(dia),
            "cierre": CierreDia.objects.filter(fecha=dia).select_related("cerrado_por").first(),
            "hoy": hoy(),
            "anteriores": CierreDia.objects.select_related("cerrado_por")[:10],
        },
    )


@requiere_permiso("cierre_dia")
@require_POST
def cerrar(request):
    dia = _fecha(request.POST.get("fecha"))
    try:
        texto = request.POST.get("efectivo_contado", "").strip()
        contado = leer_pesos(texto) if texto else None
        servicios.registrar_cierre(
            request.user, dia=dia, efectivo_contado=contado, nota=request.POST.get("nota", "")
        )
    except (ValueError, ReglaNegocio) as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"Día {dia:%d/%m/%Y} cerrado.")
    return redirect(f"{reverse('reportes:cierre')}?fecha={dia.isoformat()}")


@requiere_permiso("estadisticas")
def estadisticas(request):
    try:
        dias = int(request.GET.get("dias", 30))
    except ValueError:
        dias = 30
    if dias not in _PERIODOS:
        dias = 30
    return render(
        request,
        "reportes/estadisticas.html",
        {"e": servicios.estadisticas(dias), "dias": dias, "periodos": _PERIODOS},
    )
