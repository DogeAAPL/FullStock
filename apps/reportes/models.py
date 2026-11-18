from django.conf import settings
from django.db import models


class CierreDia(models.Model):
    """Foto de los números de un día al cerrar caja. Uno por día; no se edita.

    Si después se anula una venta de ese día, el cierre guardado no cambia: es
    lo que había cuando se contó la caja. La pantalla muestra la diferencia.
    """

    fecha = models.DateField(unique=True)
    cerrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    cerrado_en = models.DateTimeField(auto_now_add=True)
    cantidad_ventas = models.PositiveIntegerField()
    ventas_contado = models.BigIntegerField()
    ventas_fiado = models.BigIntegerField()
    abonos = models.BigIntegerField()
    gastos_pedidos = models.BigIntegerField()
    efectivo_esperado = models.BigIntegerField()
    efectivo_contado = models.BigIntegerField(null=True, blank=True)
    nota = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "cierre del día"
        verbose_name_plural = "cierres del día"

    def __str__(self) -> str:
        return f"Cierre {self.fecha}"

    @property
    def diferencia(self) -> int | None:
        if self.efectivo_contado is None:
            return None
        return self.efectivo_contado - self.efectivo_esperado
