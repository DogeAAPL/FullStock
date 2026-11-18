from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.nucleo.cantidades import Unidad
from apps.nucleo.texto import normalizar


class Producto(models.Model):
    nombre = models.CharField(max_length=120)
    # Minúsculas y sin tildes: para buscar y avisar de posibles duplicados.
    nombre_normalizado = models.CharField(max_length=120, db_index=True, editable=False)
    unidad = models.CharField(max_length=3, choices=Unidad.choices)
    precio = models.PositiveIntegerField("precio de venta ($ por unidad)")
    # Existencia derivada: la escribe SOLO inventario.servicios, en la misma
    # transacción que el movimiento. Ninguna pantalla la edita. Unidad mínima
    # (unidades o gramos). Puede quedar negativa si se vende sin existencia.
    existencia = models.BigIntegerField(default=0, editable=False)
    activo = models.BooleanField(default=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]
        constraints = [
            models.CheckConstraint(
                condition=Q(unidad__in=Unidad.values), name="producto_unidad_valida"
            ),
        ]

    def __str__(self) -> str:
        return self.nombre

    def save(self, *args, **kwargs):
        self.nombre_normalizado = normalizar(self.nombre)
        super().save(*args, **kwargs)
