import uuid

from django.urls import reverse

from apps.fiados.models import Cliente
from apps.ventas import servicios
from apps.ventas.models import Venta
from apps.ventas.servicios import LineaNueva


def test_flujo_completo_de_venta(cliente_web, colaborador, tomate, atun):
    web = cliente_web(colaborador)
    assert web.get(reverse("ventas:vender")).status_code == 200

    respuesta = web.post(
        reverse("ventas:agregar"), {"producto_id": tomate.pk, "cantidad": "1,5", "precio": "3.000"}
    )
    assert "$ 4.500" in respuesta.content.decode()
    web.post(
        reverse("ventas:agregar"), {"producto_id": atun.pk, "cantidad": "2", "precio": "4.500"}
    )

    respuesta = web.post(reverse("ventas:guardar"))
    assert respuesta.status_code == 204
    assert respuesta["HX-Redirect"] == reverse("ventas:vender")
    venta = Venta.objects.get()
    assert venta.total == 13_500
    assert venta.usuario == colaborador
    # El carrito queda vacío y con token nuevo.
    assert "Busca un producto" in web.get(reverse("ventas:vender")).content.decode()


def test_cantidad_invalida_muestra_error(cliente_web, colaborador, atun):
    web = cliente_web(colaborador)
    respuesta = web.post(
        reverse("ventas:agregar"), {"producto_id": atun.pk, "cantidad": "1,5", "precio": "4500"}
    )
    assert "unidades enteras" in respuesta.content.decode()


def test_venta_fiada_con_cliente_nuevo(cliente_web, colaborador, tomate):
    web = cliente_web(colaborador)
    web.post(
        reverse("ventas:agregar"), {"producto_id": tomate.pk, "cantidad": "1", "precio": "3000"}
    )
    web.post(reverse("ventas:guardar"), {"es_fiado": "on", "cliente_nuevo": "Doña Rosa"})
    cliente = Cliente.objects.get(nombre="Doña Rosa")
    assert cliente.saldo == 3_000


def test_fiado_sin_cliente_muestra_error(cliente_web, colaborador, tomate):
    web = cliente_web(colaborador)
    web.post(
        reverse("ventas:agregar"), {"producto_id": tomate.pk, "cantidad": "1", "precio": "3000"}
    )
    respuesta = web.post(reverse("ventas:guardar"), {"es_fiado": "on"})
    assert "Elige o crea el cliente" in respuesta.content.decode()
    assert not Venta.objects.exists()


def test_corregir_desde_ventas_de_hoy(cliente_web, dueno, colaborador, tomate):
    venta = servicios.registrar_venta(
        usuario=colaborador, lineas=[LineaNueva(tomate.pk, 1_000, 3_000)], token=uuid.uuid4()
    )
    web = cliente_web(dueno)
    web.post(reverse("ventas:corregir", args=[venta.pk]))
    pagina = web.get(reverse("ventas:vender")).content.decode()
    assert "Estás corrigiendo la venta" in pagina
    web.post(reverse("ventas:quitar", args=[0]))
    web.post(
        reverse("ventas:agregar"), {"producto_id": tomate.pk, "cantidad": "2", "precio": "3000"}
    )
    web.post(reverse("ventas:guardar"))
    venta.refresh_from_db()
    assert venta.anulada
    assert venta.corregida_por.total == 6_000


def test_ventas_de_hoy_no_hace_consultas_por_fila(
    cliente_web, dueno, tomate, atun, django_assert_max_num_queries
):
    for _ in range(15):
        servicios.registrar_venta(
            usuario=dueno,
            lineas=[LineaNueva(tomate.pk, 500, 3_000), LineaNueva(atun.pk, 1, 4_500)],
            token=uuid.uuid4(),
        )
    web = cliente_web(dueno)
    # Número fijo de consultas aunque haya muchas ventas (sin N+1).
    with django_assert_max_num_queries(12):
        assert web.get(reverse("ventas:hoy")).status_code == 200


def test_inventario_lista_sin_n_mas_1(
    cliente_web, dueno, crear_producto, django_assert_max_num_queries
):
    for i in range(30):
        crear_producto(f"Producto {i}", "und", 1000, "5")
    web = cliente_web(dueno)
    with django_assert_max_num_queries(10):
        assert web.get(reverse("inventario:lista")).status_code == 200
