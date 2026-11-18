"""Carga datos de demostración si la base está vacía.

    python manage.py cargar_demo

Usuarios (usuario / PIN):
- jeancarlo / 1234 — dueño
- esposa / 5678 — colaboradora con permisos por defecto
- hermano / 9012 — colaborador que solo puede vender

No hace nada si ya hay usuarios, así que se puede correr en cada arranque.
"""

import uuid
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.fiados.models import Cliente
from apps.inventario import servicios as inventario
from apps.inventario.models import MotivoAjuste
from apps.nucleo.cantidades import Unidad
from apps.usuarios import servicios as usuarios
from apps.ventas import servicios as ventas
from apps.ventas.servicios import LineaNueva

_PRODUCTOS = (
    ("Tomate chonto", Unidad.KILO, 3_000, "12.5"),
    ("Atún lata", Unidad.UNIDAD, 4_500, "18"),
    ("Papa pastusa", Unidad.KILO, 2_800, "35"),
    ("Cebolla cabezona", Unidad.KILO, 3_500, "8"),
    ("Gaseosa 1,5 L", Unidad.UNIDAD, 5_600, "24"),
    ("Arroz 500 g", Unidad.UNIDAD, 2_500, "40"),
    ("Huevos (unidad)", Unidad.UNIDAD, 600, "90"),
    ("Leche entera 1 L", Unidad.UNIDAD, 4_200, "20"),
    ("Panela", Unidad.LIBRA, 2_400, "15"),
    ("Aceite 1 L", Unidad.UNIDAD, 11_500, "10"),
)


class Command(BaseCommand):
    help = "Carga usuarios, productos y ventas de ejemplo si la base está vacía."

    @transaction.atomic
    def handle(self, *args, **options):
        if usuarios.hay_usuarios():
            self.stdout.write("Ya hay datos; no se carga la demostración.")
            return

        dueno, _ = usuarios.crear_dueno("Jean Carlo", "jeancarlo", "1234", "1234")
        esposa = usuarios.crear_colaborador(dueno, "Esposa", "esposa", "5678", "5678")
        hermano = usuarios.crear_colaborador(
            dueno, "Hermano", "hermano", "9012", "9012", permisos={"vender"}
        )

        p = {
            nombre: inventario.dar_de_alta_producto(
                dueno, nombre=nombre, unidad=unidad, precio=precio, cantidad_inicial=Decimal(cant)
            )
            for nombre, unidad, precio, cant in _PRODUCTOS
        }
        clientes = [Cliente.objects.create(nombre=f"Cliente {i}") for i in (1, 2, 3)]

        def vender(quien, *lineas, cliente=None):
            ventas.registrar_venta(
                usuario=quien,
                lineas=[LineaNueva(p[n].pk, c, p[n].precio) for n, c in lineas],
                token=uuid.uuid4(),
                cliente_id=cliente.pk if cliente else None,
            )

        vender(dueno, ("Tomate chonto", 1_500), ("Atún lata", 2), ("Papa pastusa", 3_000))
        vender(esposa, ("Papa pastusa", 2_000))
        vender(hermano, ("Atún lata", 3))
        vender(esposa, ("Arroz 500 g", 2), ("Huevos (unidad)", 12), cliente=clientes[0])
        vender(dueno, ("Gaseosa 1,5 L", 2), ("Panela", 500))
        inventario.corregir_existencia(
            dueno,
            producto_id=p["Cebolla cabezona"].pk,
            nueva_cantidad=7_000,
            motivo=MotivoAjuste.CONTEO,
        )
        self.stdout.write(self.style.SUCCESS("Datos de demostración cargados."))
