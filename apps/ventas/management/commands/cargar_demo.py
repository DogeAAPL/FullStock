"""Carga datos de demostración por partes; cada parte solo se carga si falta.

    python manage.py cargar_demo

Usuarios (usuario / PIN):
- jeancarlo / 1234 — dueño
- esposa / 5678 — colaboradora con permisos por defecto
- hermano / 9012 — colaborador que solo puede vender

Se puede correr en cada arranque: lo que ya existe no se vuelve a cargar.
SOLO PARA DEMOSTRACIÓN: el historial de ventas se fecha hacia atrás para que
las estadísticas tengan datos; en la tienda real nunca se cambian fechas.
"""

import random
import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.catalogo.models import Producto
from apps.fiados import servicios as fiados
from apps.fiados.models import Cliente, MovimientoFiado, TipoMovimientoFiado
from apps.inventario import servicios as inventario
from apps.inventario.models import MotivoAjuste
from apps.nucleo.cantidades import Unidad
from apps.nucleo.fechas import hoy
from apps.pedidos import servicios as pedidos
from apps.pedidos.models import Proveedor
from apps.usuarios import servicios as usuarios
from apps.usuarios.models import Usuario
from apps.ventas import servicios as ventas
from apps.ventas.models import Venta
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
# Cuánto se vende típicamente de cada producto en una línea (unidad mínima).
_PORCIONES = {Unidad.UNIDAD: (1, 3), Unidad.KILO: (500, 2_000), Unidad.LIBRA: (500, 1_000)}


def _vender(quien, productos, *lineas, cliente=None) -> Venta:
    return ventas.registrar_venta(
        usuario=quien,
        lineas=[LineaNueva(productos[n].pk, c, productos[n].precio) for n, c in lineas],
        token=uuid.uuid4(),
        cliente_id=cliente.pk if cliente else None,
    )


class Command(BaseCommand):
    help = "Carga usuarios, productos, ventas, pedidos y fiados de ejemplo."

    @transaction.atomic
    def handle(self, *args, **options):
        partes = [
            ("usuarios y ventas de hoy", self._base),
            ("proveedores y pedidos", self._pedidos),
            ("historial de ventas", self._historial),
            ("abonos y cierre de ayer", self._fiados_y_cierre),
        ]
        for nombre, parte in partes:
            if parte():
                self.stdout.write(f"Cargado: {nombre}.")
        self.stdout.write(self.style.SUCCESS("Datos de demostración listos."))

    def _actores(self):
        u = {x.usuario: x for x in Usuario.objects.all()}
        return u["jeancarlo"], u["esposa"], u["hermano"]

    def _productos(self) -> dict[str, Producto]:
        return {p.nombre: p for p in Producto.objects.all()}

    def _base(self) -> bool:
        if usuarios.hay_usuarios():
            return False
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
        _vender(dueno, p, ("Tomate chonto", 1_500), ("Atún lata", 2), ("Papa pastusa", 3_000))
        _vender(esposa, p, ("Papa pastusa", 2_000))
        _vender(hermano, p, ("Atún lata", 3))
        _vender(esposa, p, ("Arroz 500 g", 2), ("Huevos (unidad)", 12), cliente=clientes[0])
        _vender(dueno, p, ("Gaseosa 1,5 L", 2), ("Panela", 500))
        inventario.corregir_existencia(
            dueno,
            producto_id=p["Cebolla cabezona"].pk,
            nueva_cantidad=7_000,
            motivo=MotivoAjuste.CONTEO,
        )
        return True

    def _pedidos(self) -> bool:
        if Proveedor.objects.exists():
            return False
        dueno, esposa, _ = self._actores()
        p = self._productos()
        a = pedidos.crear_proveedor(dueno, "Distribuidora La Cosecha", "300 000 0000")
        b = pedidos.crear_proveedor(dueno, "Enlatados del Valle")
        c = pedidos.crear_proveedor(dueno, "Bebidas Pacífico", "315 000 0000")
        # Reabastecimiento ya recibido (sube el inventario para el historial).
        for nombre, proveedor, cantidad, costo, dias in (
            ("Tomate chonto", a, 60_000, 2_200, 30),
            ("Papa pastusa", a, 60_000, 1_900, 30),
            ("Atún lata", b, 96, 3_600, 30),
            ("Gaseosa 1,5 L", c, 96, 4_200, 30),
            ("Arroz 500 g", a, 96, 1_900, 30),
            ("Huevos (unidad)", a, 180, 420, 30),
            ("Leche entera 1 L", c, 96, 3_300, 30),
            ("Panela", a, 30_000, 1_800, 30),
            ("Aceite 1 L", b, 96, 9_200, 30),
            ("Cebolla cabezona", a, 60_000, 2_600, 30),
        ):
            pedido = pedidos.crear_pedido(
                dueno,
                producto_id=p[nombre].pk,
                proveedor_id=proveedor.pk,
                cantidad=cantidad,
                costo_unitario=costo,
                fecha_pedido=hoy() - timedelta(days=dias),
            )
            pedidos.recibir_pedido(
                dueno,
                pedido_id=pedido.pk,
                cantidad_recibida=cantidad,
                costo_unitario=costo,
                fecha_llegada=hoy() - timedelta(days=dias - 1),
            )
        # Pendientes, como en los diseños.
        for nombre, proveedor, cantidad, costo, dias, quien in (
            ("Cebolla cabezona", a, 20_000, 2_600, 9, dueno),
            ("Papa pastusa", a, 50_000, 2_200, 7, esposa),
            ("Atún lata", b, 24, 3_900, 4, esposa),
            ("Tomate chonto", a, 10_000, 4_500, 2, dueno),
        ):
            pedidos.crear_pedido(
                quien,
                producto_id=p[nombre].pk,
                proveedor_id=proveedor.pk,
                cantidad=cantidad,
                costo_unitario=costo,
                fecha_pedido=hoy() - timedelta(days=dias),
            )
        return True

    def _historial(self) -> bool:
        inicio_hoy = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        if Venta.objects.filter(fecha__lt=inicio_hoy).exists():
            return False
        actores = self._actores()
        p = self._productos()
        clientes = list(Cliente.objects.all())
        azar = random.Random(20261118)
        nombres = list(p)
        for dias_atras in range(29, 0, -1):
            dia = hoy() - timedelta(days=dias_atras)
            for _ in range(azar.randint(3, 7)):
                lineas = []
                for nombre in azar.sample(nombres, azar.randint(1, 3)):
                    minimo, maximo = _PORCIONES[Unidad(p[nombre].unidad)]
                    lineas.append((nombre, azar.randint(minimo, maximo) // 50 * 50 or minimo))
                fiado = azar.random() < 0.15
                # El hermano solo vende de contado (no tiene permiso de fiar).
                vendedor = azar.choice(actores[:2] if fiado else actores)
                venta = _vender(
                    vendedor,
                    p,
                    *lineas,
                    cliente=azar.choice(clientes) if fiado else None,
                )
                momento = timezone.make_aware(
                    timezone.datetime.combine(dia, timezone.datetime.min.time())
                ) + timedelta(hours=azar.randint(8, 20), minutes=azar.randint(0, 59))
                # Solo demostración: se mueve la venta al día que le corresponde.
                Venta.objects.filter(pk=venta.pk).update(fecha=momento)
        return True

    def _fiados_y_cierre(self) -> bool:
        if MovimientoFiado.objects.filter(tipo=TipoMovimientoFiado.ABONO).exists():
            return False
        dueno, _, _ = self._actores()
        for cliente in Cliente.objects.filter(saldo__gt=10_000):
            fiados.registrar_abono(dueno, cliente_id=cliente.pk, monto=cliente.saldo // 2)
        p = self._productos()
        inventario.corregir_existencia(
            dueno,
            producto_id=p["Leche entera 1 L"].pk,
            nueva_cantidad=max(Producto.objects.get(pk=p["Leche entera 1 L"].pk).existencia - 2, 0),
            motivo=MotivoAjuste.DANO,
        )
        return True
