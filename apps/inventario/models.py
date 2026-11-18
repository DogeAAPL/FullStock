from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.catalogo.models import Producto


class TipoMovimiento(models.TextChoices):
    INICIAL = "inicial", "Cantidad inicial"
    VENTA = "venta", "Venta"
    ANULACION_VENTA = "anulacion_venta", "Anulación de venta"
    RECEPCION = "recepcion", "Recepción de pedido"
    AJUSTE = "ajuste", "Corrección"


class MotivoAjuste(models.TextChoices):
    CONTEO = "conteo", "Conteo"
    DANO = "dano", "Daño"
    PERDIDA = "perdida", "Pérdida"
    OTRO = "otro", "Otro"


class MovimientoInventario(models.Model):
    """Historia del inventario. Tabla de solo inserción (trigger en la migración).

    La existencia de un producto es la suma de sus movimientos. Un error se
    corrige con otro movimiento, nunca editando o borrando uno anterior.
    """

    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="movimientos")
    tipo = models.CharField(max_length=20, choices=TipoMovimiento.choices)
    motivo = models.CharField(max_length=10, choices=MotivoAjuste.choices, blank=True)
    # Unidad mínima del producto, con signo: + entra, − sale.
    cantidad = models.BigIntegerField()
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)
    # Qué lo originó, p. ej. "venta:15" o "pedido:3". Texto para no acoplar apps.
    origen = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        indexes = [models.Index(fields=["producto", "fecha"], name="mov_producto_fecha")]
        constraints = [
            models.CheckConstraint(condition=~Q(cantidad=0), name="mov_cantidad_no_cero"),
            models.CheckConstraint(
                condition=~Q(tipo="ajuste") | ~Q(motivo=""), name="mov_ajuste_con_motivo"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {self.cantidad} de {self.producto_id}"
