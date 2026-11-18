from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.catalogo.models import Producto
from apps.fiados.models import Cliente


class Venta(models.Model):
    """Una venta nunca se edita ni se borra: se anula, y corregirla crea otra enlazada."""

    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ventas"
    )
    total = models.PositiveBigIntegerField(default=0)
    es_fiado = models.BooleanField(default=False)
    cliente = models.ForeignKey(Cliente, null=True, blank=True, on_delete=models.PROTECT)
    # Único por formulario: un doble clic en "Guardar" no registra la venta dos veces.
    token = models.UUIDField(unique=True)
    corrige_a = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="corregida_por"
    )
    anulada = models.BooleanField(default=False)
    anulada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="ventas_anuladas",
    )
    anulada_en = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-fecha"]
        constraints = [
            models.CheckConstraint(
                condition=Q(es_fiado=False) | Q(cliente__isnull=False),
                name="venta_fiada_con_cliente",
            ),
            models.CheckConstraint(
                condition=Q(anulada=False) | Q(anulada_en__isnull=False),
                name="venta_anulada_con_fecha",
            ),
        ]

    def __str__(self) -> str:
        return f"Venta {self.pk}"


class LineaVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.PROTECT, related_name="lineas")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    # Unidad mínima del producto (unidades o gramos).
    cantidad = models.PositiveBigIntegerField()
    # Precio cobrado en el momento, por unidad de venta. Puede diferir del de catálogo.
    precio = models.PositiveIntegerField()
    subtotal = models.PositiveBigIntegerField()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=Q(cantidad__gt=0), name="linea_cantidad_positiva"),
        ]

    def __str__(self) -> str:
        return f"{self.producto_id} × {self.cantidad}"
