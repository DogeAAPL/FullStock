from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.nucleo.texto import normalizar


class Cliente(models.Model):
    nombre = models.CharField(max_length=120)
    nombre_normalizado = models.CharField(max_length=120, db_index=True, editable=False)
    telefono = models.CharField(max_length=30, blank=True)
    # Saldo derivado de los movimientos; solo lo escribe fiados.servicios.
    saldo = models.BigIntegerField(default=0, editable=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self) -> str:
        return self.nombre

    def save(self, *args, **kwargs):
        self.nombre_normalizado = normalizar(self.nombre)
        super().save(*args, **kwargs)


class TipoMovimientoFiado(models.TextChoices):
    CARGO = "cargo", "Fiado"
    ABONO = "abono", "Abono"
    REVERSION = "reversion", "Reversión por anulación"


class MovimientoFiado(models.Model):
    """Cargos y abonos de un cliente. Tabla de solo inserción.

    Monto en pesos con signo: + aumenta la deuda, − la disminuye.
    """

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="movimientos")
    tipo = models.CharField(max_length=10, choices=TipoMovimientoFiado.choices)
    monto = models.BigIntegerField()
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)
    origen = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        indexes = [
            models.Index(fields=["cliente", "fecha"], name="movfiado_cliente_fecha"),
            models.Index(fields=["tipo", "fecha"], name="movfiado_tipo_fecha"),
        ]
        constraints = [
            models.CheckConstraint(condition=~Q(monto=0), name="movfiado_monto_no_cero"),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {self.monto} de {self.cliente_id}"
