from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from .permisos import CATALOGO

# Límites de la configuración: impiden dejar la app insegura por accidente.
LIMITES = {
    "minutos_inactividad": (2, 120),
    "intentos_pin": (3, 10),
    "minutos_bloqueo": (5, 60),
    "horas_respaldo": (1, 24),
}


def _rango(campo: str) -> list:
    minimo, maximo = LIMITES[campo]
    return [MinValueValidator(minimo), MaxValueValidator(maximo)]


def _check_rango(campo: str) -> models.CheckConstraint:
    minimo, maximo = LIMITES[campo]
    return models.CheckConstraint(
        condition=Q(**{f"{campo}__gte": minimo, f"{campo}__lte": maximo}),
        name=f"configuracion_{campo}_rango",
    )


class Configuracion(models.Model):
    """Ajustes que el dueño cambia desde su panel. Una sola fila (pk=1)."""

    minutos_inactividad = models.PositiveSmallIntegerField(
        "Minutos de inactividad antes de bloquear la sesión",
        default=10,
        validators=_rango("minutos_inactividad"),
    )
    intentos_pin = models.PositiveSmallIntegerField(
        "Intentos fallidos de PIN antes del bloqueo",
        default=5,
        validators=_rango("intentos_pin"),
    )
    minutos_bloqueo = models.PositiveSmallIntegerField(
        "Minutos de bloqueo tras intentos fallidos",
        default=10,
        validators=_rango("minutos_bloqueo"),
    )
    vender_sin_existencia = models.BooleanField(
        "Permitir vender con inventario registrado en cero",
        default=True,
        help_text="Si está activo, la venta se guarda y el inventario puede quedar negativo.",
    )
    limite_deuda = models.PositiveIntegerField(
        "Límite de deuda por cliente ($)",
        null=True,
        blank=True,
        help_text="Déjalo vacío para no tener límite.",
    )
    horas_respaldo = models.PositiveSmallIntegerField(
        "Frecuencia del respaldo automático (horas)",
        default=4,
        validators=_rango("horas_respaldo"),
    )
    carpeta_usb = models.CharField("Carpeta de respaldo en USB", max_length=260, blank=True)

    class Meta:
        verbose_name = "configuración"
        default_permissions = ()
        # Los permisos delegables viven aquí para usar el sistema de Django.
        permissions = [(p.codigo, p.nombre) for p in CATALOGO]
        constraints = [
            models.CheckConstraint(condition=Q(pk=1), name="configuracion_fila_unica"),
            *[_check_rango(c) for c in LIMITES],
        ]

    def __str__(self) -> str:
        return "Configuración de la tienda"

    @classmethod
    def cargar(cls) -> "Configuracion":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Bitacora(models.Model):
    """Registro de solo inserción: quién hizo qué y cuándo."""

    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT
    )
    accion = models.CharField(max_length=60, db_index=True)
    detalle = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "registro de bitácora"
        verbose_name_plural = "bitácora"
        ordering = ["-fecha"]

    def __str__(self) -> str:
        return f"{self.fecha:%Y-%m-%d %H:%M} {self.accion}"
