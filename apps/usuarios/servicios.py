"""Reglas de usuarios: PIN, bloqueo por intentos, clave de recuperación y permisos."""

import re
import secrets
from collections.abc import Iterable
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import Permission
from django.db import transaction
from django.utils import timezone

from apps.nucleo import servicios as nucleo
from apps.nucleo.errores import ReglaNegocio
from apps.nucleo.models import Configuracion
from apps.nucleo.permisos import APP_LABEL, CODIGOS, POR_DEFECTO

from .models import Usuario

_PIN = re.compile(r"^\d{4}$")
_USUARIO = re.compile(r"^[a-z0-9._-]{3,30}$")
# Sin letras ni números que se confunden al copiar a mano (O/0, I/1, L).
_ALFABETO_CLAVE = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_MENSAJE_FALLIDO = "Usuario o PIN incorrecto."


# --- Validaciones -----------------------------------------------------------


def validar_pin(pin: str, repetido: str | None = None) -> None:
    if not _PIN.match(pin or ""):
        raise ReglaNegocio("El PIN debe tener exactamente 4 dígitos.")
    if repetido is not None and pin != repetido:
        raise ReglaNegocio("Los dos PIN no coinciden.")


def normalizar_usuario(usuario: str) -> str:
    valor = (usuario or "").strip().lower()
    if not _USUARIO.match(valor):
        raise ReglaNegocio(
            "El usuario debe tener entre 3 y 30 caracteres, sin espacios ni tildes "
            "(letras, números, punto, guion)."
        )
    return valor


def _validar_nombre(nombre: str) -> str:
    nombre = " ".join((nombre or "").split())
    if not nombre:
        raise ReglaNegocio("Escribe el nombre.")
    return nombre


# --- Clave de recuperación --------------------------------------------------


def generar_clave() -> str:
    crudo = "".join(secrets.choice(_ALFABETO_CLAVE) for _ in range(16))
    return "-".join(crudo[i : i + 4] for i in range(0, 16, 4))


def _normalizar_clave(clave: str) -> str:
    return "".join(c for c in (clave or "").upper() if c.isalnum())


def _asignar_clave_nueva(usuario: Usuario) -> str:
    clave = generar_clave()
    usuario.clave_recuperacion = make_password(_normalizar_clave(clave))
    return clave


# --- Alta de usuarios -------------------------------------------------------


def hay_usuarios() -> bool:
    return Usuario.objects.exists()


@transaction.atomic
def crear_dueno(nombre: str, usuario: str, pin: str, pin_repetido: str) -> tuple[Usuario, str]:
    """Primer arranque. Devuelve el dueño y la clave de recuperación (se muestra una vez)."""
    if hay_usuarios():
        raise ReglaNegocio("La tienda ya tiene dueño.")
    validar_pin(pin, pin_repetido)
    dueno = Usuario(
        nombre=_validar_nombre(nombre), usuario=normalizar_usuario(usuario), es_dueno=True
    )
    dueno.set_password(pin)
    clave = _asignar_clave_nueva(dueno)
    dueno.save()
    nucleo.registrar(dueno, "usuarios.primer_arranque")
    return dueno, clave


@transaction.atomic
def crear_colaborador(
    por: Usuario,
    nombre: str,
    usuario: str,
    pin: str,
    pin_repetido: str,
    permisos: Iterable[str] | None = None,
) -> Usuario:
    _exigir_dueno(por)
    validar_pin(pin, pin_repetido)
    usuario = normalizar_usuario(usuario)
    if Usuario.objects.filter(usuario=usuario).exists():
        raise ReglaNegocio(f"Ya existe el usuario «{usuario}».")
    colaborador = Usuario(nombre=_validar_nombre(nombre), usuario=usuario)
    colaborador.set_password(pin)
    colaborador.save()
    nucleo.registrar(por, "usuarios.crear", usuario=usuario)
    asignar_permisos(por, colaborador, POR_DEFECTO if permisos is None else permisos)
    return colaborador


@transaction.atomic
def actualizar_colaborador(
    por: Usuario,
    colaborador: Usuario,
    *,
    nombre: str,
    activo: bool,
    permisos: Iterable[str],
    pin: str = "",
    pin_repetido: str = "",
) -> Usuario:
    _exigir_dueno(por)
    if colaborador.es_dueno:
        raise ReglaNegocio("El dueño tiene todos los permisos y no se puede desactivar.")
    colaborador.nombre = _validar_nombre(nombre)
    if colaborador.is_active != activo:
        colaborador.is_active = activo
        nucleo.registrar(por, "usuarios.activo", usuario=colaborador.usuario, activo=activo)
    if pin or pin_repetido:
        validar_pin(pin, pin_repetido)
        colaborador.set_password(pin)
        colaborador.intentos_fallidos = 0
        colaborador.bloqueado_hasta = None
        nucleo.registrar(por, "usuarios.cambio_pin", usuario=colaborador.usuario)
    colaborador.save()
    asignar_permisos(por, colaborador, permisos)
    return colaborador


# --- Permisos ---------------------------------------------------------------


def permisos_de(usuario: Usuario) -> set[str]:
    if usuario.es_dueno:
        return set(CODIGOS)
    return set(
        usuario.user_permissions.filter(content_type__app_label=APP_LABEL).values_list(
            "codename", flat=True
        )
    )


@transaction.atomic
def asignar_permisos(por: Usuario, colaborador: Usuario, codigos: Iterable[str]) -> None:
    """Deja al colaborador exactamente con estos permisos y lo anota en la bitácora."""
    _exigir_dueno(por)
    if colaborador.es_dueno:
        raise ReglaNegocio("El dueño ya tiene todos los permisos.")
    nuevos = set(codigos)
    desconocidos = nuevos - CODIGOS
    if desconocidos:
        raise ReglaNegocio(f"Permisos desconocidos: {', '.join(sorted(desconocidos))}")
    antes = permisos_de(colaborador)
    if antes == nuevos:
        return
    colaborador.user_permissions.set(
        Permission.objects.filter(content_type__app_label=APP_LABEL, codename__in=nuevos)
    )
    # Django guarda en caché los permisos del objeto; se limpian para que apliquen ya.
    for cache in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        colaborador.__dict__.pop(cache, None)
    nucleo.registrar(
        por,
        "usuarios.permisos",
        usuario=colaborador.usuario,
        activados=sorted(nuevos - antes),
        desactivados=sorted(antes - nuevos),
    )


# --- Inicio de sesión -------------------------------------------------------


def autenticar(usuario: str, pin: str, config: Configuracion | None = None) -> Usuario:
    """Valida usuario y PIN con bloqueo tras varios intentos fallidos."""
    config = config or Configuracion.cargar()
    nombre_usuario = (usuario or "").strip().lower()
    candidato = Usuario.objects.filter(usuario=nombre_usuario, is_active=True).first()
    if candidato is None:
        make_password(pin)  # mismo tiempo de respuesta exista o no el usuario
        nucleo.registrar(None, "usuarios.login_fallido", usuario=nombre_usuario)
        raise ReglaNegocio(_MENSAJE_FALLIDO)

    _exigir_no_bloqueado(candidato)
    if candidato.check_password(pin):
        _limpiar_intentos(candidato)
        nucleo.registrar(candidato, "usuarios.login")
        return candidato

    _contar_intento_fallido(candidato, config)
    raise ReglaNegocio(_MENSAJE_FALLIDO)


def recuperar_con_clave(
    usuario: str, clave: str, pin: str, pin_repetido: str
) -> tuple[Usuario, str]:
    """El dueño entra con su clave de papel, fija un PIN nuevo y recibe una clave nueva.

    Sin transacción envolvente a propósito: el intento fallido debe quedar
    guardado aunque la función termine con error.
    """
    validar_pin(pin, pin_repetido)
    config = Configuracion.cargar()
    dueno = Usuario.objects.filter(
        usuario=(usuario or "").strip().lower(), es_dueno=True, is_active=True
    ).first()
    mensaje = "Usuario o clave de recuperación incorrectos."
    if dueno is None or not dueno.clave_recuperacion:
        raise ReglaNegocio(mensaje)
    _exigir_no_bloqueado(dueno)
    if not check_password(_normalizar_clave(clave), dueno.clave_recuperacion):
        _contar_intento_fallido(dueno, config)
        raise ReglaNegocio(mensaje)
    with transaction.atomic():
        dueno.set_password(pin)
        nueva_clave = _asignar_clave_nueva(dueno)  # la anterior ya quedó expuesta
        dueno.intentos_fallidos = 0
        dueno.bloqueado_hasta = None
        dueno.save()
        nucleo.registrar(dueno, "usuarios.recuperacion")
    return dueno, nueva_clave


# --- Auxiliares -------------------------------------------------------------


def _exigir_dueno(por: Usuario) -> None:
    if not (por and por.is_authenticated and por.es_dueno):
        raise ReglaNegocio("Solo el dueño puede hacer esto.")


def _exigir_no_bloqueado(usuario: Usuario) -> None:
    if usuario.bloqueado_hasta and usuario.bloqueado_hasta > timezone.now():
        faltan = usuario.bloqueado_hasta - timezone.now()
        minutos = max(1, round(faltan.total_seconds() / 60))
        raise ReglaNegocio(f"Usuario bloqueado por intentos fallidos. Intenta en {minutos} min.")


def _limpiar_intentos(usuario: Usuario) -> None:
    if usuario.intentos_fallidos or usuario.bloqueado_hasta:
        Usuario.objects.filter(pk=usuario.pk).update(intentos_fallidos=0, bloqueado_hasta=None)
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None


def _contar_intento_fallido(usuario: Usuario, config: Configuracion) -> None:
    usuario.intentos_fallidos += 1
    if usuario.intentos_fallidos >= config.intentos_pin:
        usuario.bloqueado_hasta = timezone.now() + timedelta(minutes=config.minutos_bloqueo)
        usuario.intentos_fallidos = 0
        nucleo.registrar(None, "usuarios.bloqueo", usuario=usuario.usuario)
    else:
        nucleo.registrar(None, "usuarios.login_fallido", usuario=usuario.usuario)
    Usuario.objects.filter(pk=usuario.pk).update(
        intentos_fallidos=usuario.intentos_fallidos, bloqueado_hasta=usuario.bloqueado_hasta
    )
