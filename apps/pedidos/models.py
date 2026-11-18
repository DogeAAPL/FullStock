from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.catalogo.models import Producto
from apps.nucleo.texto import normalizar


class Proveedor(models.Model):
    nombre = models.CharField(max_length=120)
    nombre_normalizado = models.CharField(max_length=120, db_index=True, editable=False)
    telefono = models.CharField(max_length=30, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name_plural = "proveedores"

    def __str__(self) -> str:
        return self.nombre

    def save(self, *args, **kwargs):
        self.nombre_normalizado = normalizar(self.nombre)
        super().save(*args, **kwargs)


class EstadoPedido(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    RECIBIDO = "recibido", "Recibido"
    CANCELADO = "cancelado", "Cancelado"


class Pedido(models.Model):
    """Un producto pedido a un proveedor. Nunca se borra: se recibe o se cancela.

    Un pedido se recibe una sola vez. Si llega menos de lo pedido, el pedido se
    cierra con la cantidad que llegó y el faltante queda registrado.
    """

    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="pedidos")
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name="pedidos")
    # Unidad mínima del producto (unidades o gramos).
    cantidad = models.PositiveBigIntegerField()
    # Costo por unidad de venta del producto (por kilo, por libra o por unidad).
    costo_unitario = models.PositiveIntegerField()
    fecha_pedido = models.DateField()
    estado = models.CharField(
        max_length=10, choices=EstadoPedido.choices, default=EstadoPedido.PENDIENTE
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="pedidos_creados"
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    cantidad_recibida = models.PositiveBigIntegerField(null=True, blank=True)
    costo_recibido = models.PositiveIntegerField(null=True, blank=True)
    gasto = models.PositiveBigIntegerField(null=True, blank=True)
    fecha_llegada = models.DateField(null=True, blank=True)
    recibido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="pedidos_recibidos",
    )
    recibido_en = models.DateTimeField(null=True, blank=True)

    cancelado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="pedidos_cancelados",
    )
    cancelado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["fecha_pedido", "id"]
        indexes = [
            models.Index(fields=["estado", "fecha_pedido"], name="pedido_estado_fecha"),
            models.Index(fields=["producto", "estado"], name="pedido_producto_estado"),
            models.Index(fields=["recibido_en"], name="pedido_recibido_en"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(cantidad__gt=0), name="pedido_cantidad_positiva"),
            models.CheckConstraint(
                condition=~Q(estado="recibido")
                | Q(cantidad_recibida__isnull=False, gasto__isnull=False),
                name="pedido_recibido_completo",
            ),
        ]

    def __str__(self) -> str:
        return f"Pedido {self.pk} de {self.producto_id}"

    @property
    def faltante(self) -> int:
        if self.cantidad_recibida is None:
            return 0
        return max(self.cantidad - self.cantidad_recibida, 0)
