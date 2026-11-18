from decimal import Decimal

import pytest

from apps.catalogo.models import Producto
from apps.fiados.models import Cliente
from apps.inventario import servicios as inventario
from apps.nucleo.cantidades import Unidad
from apps.usuarios import servicios as usuarios


@pytest.fixture(autouse=True)
def _estaticos_simples(settings, tmp_path):
    # En pruebas no hay collectstatic: se usa el almacenamiento sin manifiesto.
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    # Hash rápido solo en pruebas; en la tienda se usa el de Django por defecto.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def dueno(db):
    usuario, _ = usuarios.crear_dueno("Jean Carlo", "jeancarlo", "1234", "1234")
    return usuario


@pytest.fixture
def crear_colaborador(dueno):
    contador = {"n": 0}

    def _crear(permisos=None, nombre="Esposa"):
        contador["n"] += 1
        return usuarios.crear_colaborador(
            dueno, nombre, f"colab{contador['n']}", "5678", "5678", permisos=permisos
        )

    return _crear


@pytest.fixture
def colaborador(crear_colaborador):
    """Colaborador con los permisos por defecto del catálogo."""
    return crear_colaborador()


@pytest.fixture
def crear_producto(dueno):
    def _crear(nombre="Tomate chonto", unidad=Unidad.KILO, precio=3000, existencia="10"):
        return inventario.dar_de_alta_producto(
            dueno,
            nombre=nombre,
            unidad=unidad,
            precio=precio,
            cantidad_inicial=Decimal(existencia) if existencia else None,
        )

    return _crear


@pytest.fixture
def tomate(crear_producto) -> Producto:
    return crear_producto()


@pytest.fixture
def atun(crear_producto) -> Producto:
    return crear_producto("Atún lata", Unidad.UNIDAD, 4500, "20")


@pytest.fixture
def cliente(db) -> Cliente:
    return Cliente.objects.create(nombre="Cliente 1")


@pytest.fixture
def cliente_web(client):
    """Cliente HTTP con una sesión iniciada como el usuario dado."""

    def _entrar(usuario):
        client.force_login(usuario, backend="django.contrib.auth.backends.ModelBackend")
        return client

    return _entrar
