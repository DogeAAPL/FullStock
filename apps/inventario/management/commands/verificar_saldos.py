"""Comprueba que cada existencia guardada coincida con la suma de sus movimientos.

    python manage.py verificar_saldos

Termina con código 1 si encuentra descuadres, para poder programarlo y alertar.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.inventario.servicios import verificar_existencias


class Command(BaseCommand):
    help = "Verifica existencias contra la suma de movimientos."

    def handle(self, *args, **options):
        descuadres = verificar_existencias()
        if not descuadres:
            self.stdout.write(self.style.SUCCESS("Todas las existencias cuadran."))
            return
        for d in descuadres:
            self.stderr.write(
                f"{d.nombre} (id {d.producto_id}): guardada {d.guardada}, calculada {d.calculada}"
            )
        raise CommandError(f"{len(descuadres)} producto(s) descuadrado(s).")
