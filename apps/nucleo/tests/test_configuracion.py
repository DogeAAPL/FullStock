import pytest
from django.db import IntegrityError, transaction

from apps.nucleo.errores import ReglaNegocio
from apps.nucleo.models import Bitacora, Configuracion
from apps.nucleo.servicios import actualizar_configuracion


def test_valores_por_defecto(db):
    config = Configuracion.cargar()
    assert config.minutos_inactividad == 10
    assert config.intentos_pin == 5
    assert config.vender_sin_existencia is True


def test_dueno_cambia_configuracion_y_queda_en_bitacora(dueno):
    actualizar_configuracion(dueno, {"minutos_inactividad": 15})
    assert Configuracion.cargar().minutos_inactividad == 15
    registro = Bitacora.objects.get(accion="configuracion.cambio")
    assert registro.detalle == {"cambios": {"minutos_inactividad": [10, 15]}}


def test_colaborador_no_cambia_configuracion(colaborador):
    with pytest.raises(ReglaNegocio):
        actualizar_configuracion(colaborador, {"minutos_inactividad": 15})


@pytest.mark.parametrize(
    "cambios",
    [{"minutos_inactividad": 1}, {"minutos_inactividad": 500}, {"intentos_pin": 0}],
)
def test_limites_impiden_configuracion_insegura(dueno, cambios):
    with pytest.raises(ReglaNegocio):
        actualizar_configuracion(dueno, cambios)


def test_limites_tambien_en_la_base_de_datos(db):
    Configuracion.cargar()
    with pytest.raises(IntegrityError), transaction.atomic():
        Configuracion.objects.filter(pk=1).update(intentos_pin=0)


def test_solo_una_fila(db):
    Configuracion.cargar()
    with pytest.raises(IntegrityError), transaction.atomic():
        Configuracion.objects.create(pk=2)


def test_bitacora_es_de_solo_insercion(dueno):
    registro = Bitacora.objects.first()
    with pytest.raises(IntegrityError), transaction.atomic():
        Bitacora.objects.filter(pk=registro.pk).update(accion="otra")
    with pytest.raises(IntegrityError), transaction.atomic():
        Bitacora.objects.filter(pk=registro.pk).delete()
