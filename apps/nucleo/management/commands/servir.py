"""Arranca FullStock en el computador de la tienda.

    python manage.py servir

Aplica migraciones pendientes y sirve la app con Waitress solo en 127.0.0.1,
así nadie en el wifi de la tienda puede abrirla.
"""

import socket

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from waitress import serve

from config.wsgi import application


class Command(BaseCommand):
    help = "Aplica migraciones y sirve FullStock en este computador."

    def add_arguments(self, parser):
        parser.add_argument("--puerto", type=int, default=8000)
        parser.add_argument("--hilos", type=int, default=4)

    def handle(self, *args, puerto: int, hilos: int, **options):
        with socket.socket() as prueba:
            if prueba.connect_ex(("127.0.0.1", puerto)) == 0:
                raise CommandError(
                    f"El puerto {puerto} ya está en uso. "
                    "¿FullStock ya está abierto en otra ventana?"
                )
        call_command("migrate", interactive=False, verbosity=0)
        self.stdout.write(self.style.SUCCESS(f"FullStock listo en http://127.0.0.1:{puerto}"))
        serve(application, host="127.0.0.1", port=puerto, threads=hilos)
