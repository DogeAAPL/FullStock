import uuid

import pytest
from django.urls import reverse

from apps.fiados import servicios
from apps.fiados.models import MovimientoFiado, TipoMovimientoFiado
from apps.nucleo.errores import ReglaNegocio
from apps.ventas import servicios as ventas
from apps.ventas.servicios import LineaNueva


def _fiar(usuario, producto, cliente, cantidad=2_000):
    return ventas.registrar_venta(
        usuario=usuario,
        lineas=[LineaNueva(producto.pk, cantidad, producto.precio)],
        token=uuid.uuid4(),
        cliente_id=cliente.pk,
    )


def test_abono_reduce_la_deuda(dueno, tomate, cliente):
    _fiar(dueno, tomate, cliente)  # $6.000
    servicios.registrar_abono(dueno, cliente_id=cliente.pk, monto=2_500)
    cliente.refresh_from_db()
    assert cliente.saldo == 3_500
    abono = MovimientoFiado.objects.get(tipo=TipoMovimientoFiado.ABONO)
    assert abono.monto == -2_500


def test_no_se_abona_mas_de_lo_que_se_debe(dueno, tomate, cliente):
    _fiar(dueno, tomate, cliente)
    with pytest.raises(ReglaNegocio, match="supera la deuda"):
        servicios.registrar_abono(dueno, cliente_id=cliente.pk, monto=6_001)
    with pytest.raises(ReglaNegocio):
        servicios.registrar_abono(dueno, cliente_id=cliente.pk, monto=0)


def test_abonar_requiere_permiso(colaborador, tomate, cliente, dueno):
    _fiar(dueno, tomate, cliente)
    with pytest.raises(ReglaNegocio, match="permiso"):
        servicios.registrar_abono(colaborador, cliente_id=cliente.pk, monto=1_000)


def test_lista_de_cobros_ordenada_por_deuda(dueno, tomate, crear_producto):
    from apps.fiados.models import Cliente

    poco = Cliente.objects.create(nombre="Debe poco")
    mucho = Cliente.objects.create(nombre="Debe mucho")
    Cliente.objects.create(nombre="No debe")
    _fiar(dueno, tomate, poco, 1_000)
    _fiar(dueno, tomate, mucho, 5_000)
    assert [c.nombre for c in servicios.clientes_para_cobrar()] == ["Debe mucho", "Debe poco"]
    assert servicios.total_por_cobrar() == 18_000
    assert len(servicios.clientes_para_cobrar(solo_con_deuda=False)) == 3


def test_limite_de_deuda_avisa(cliente):
    cliente.saldo = 40_000
    assert servicios.supera_limite(cliente, 15_000, 50_000)
    assert not servicios.supera_limite(cliente, 5_000, 50_000)
    assert not servicios.supera_limite(cliente, 1_000_000, None)


def test_pantallas(cliente_web, dueno, tomate, cliente):
    _fiar(dueno, tomate, cliente)
    web = cliente_web(dueno)
    assert "Cliente 1" in web.get(reverse("fiados:lista")).content.decode()
    web.post(reverse("fiados:abonar", args=[cliente.pk]), {"monto": "6.000"})
    cliente.refresh_from_db()
    assert cliente.saldo == 0
    pagina = web.get(reverse("fiados:cliente", args=[cliente.pk])).content.decode()
    assert "Abono" in pagina
    web.post(
        reverse("fiados:editar_cliente", args=[cliente.pk]),
        {"nombre": "Doña Rosa", "telefono": "311"},
    )
    cliente.refresh_from_db()
    assert (cliente.nombre, cliente.telefono) == ("Doña Rosa", "311")
