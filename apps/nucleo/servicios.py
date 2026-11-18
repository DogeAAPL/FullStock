from django.core.exceptions import ValidationError
from django.db import transaction

from .errores import ReglaNegocio
from .models import Bitacora, Configuracion

CAMPOS_CONFIGURACION = (
    "minutos_inactividad",
    "intentos_pin",
    "minutos_bloqueo",
    "vender_sin_existencia",
    "limite_deuda",
    "horas_respaldo",
    "carpeta_usb",
)


def registrar(actor, accion: str, /, **detalle) -> Bitacora:
    """Agrega una entrada a la bitácora. `actor` puede ser None (p. ej. intento fallido)."""
    if actor is not None and not actor.is_authenticated:
        actor = None
    return Bitacora.objects.create(usuario=actor, accion=accion, detalle=detalle)


@transaction.atomic
def actualizar_configuracion(por, cambios: dict) -> Configuracion:
    if not por.es_dueno:
        raise ReglaNegocio("Solo el dueño puede cambiar la configuración.")
    desconocidos = set(cambios) - set(CAMPOS_CONFIGURACION)
    if desconocidos:
        raise ReglaNegocio(f"Ajustes desconocidos: {', '.join(sorted(desconocidos))}")

    config = Configuracion.cargar()
    antes = {c: getattr(config, c) for c in cambios}
    for campo, valor in cambios.items():
        setattr(config, campo, valor)
    try:
        config.full_clean()
    except ValidationError as error:
        raise ReglaNegocio("; ".join(error.messages)) from error
    config.save()

    diferencias = {c: [antes[c], cambios[c]] for c in cambios if antes[c] != cambios[c]}
    if diferencias:
        registrar(por, "configuracion.cambio", cambios=diferencias)
    return config
