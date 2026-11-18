import re
from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.nucleo.errores import ReglaNegocio
from apps.nucleo.models import Bitacora, Configuracion
from apps.nucleo.permisos import CODIGOS, POR_DEFECTO
from apps.usuarios import servicios
from apps.usuarios.models import Usuario

# --- Primer arranque y dueño ------------------------------------------------


def test_crear_dueno_devuelve_clave_de_recuperacion(db):
    dueno, clave = servicios.crear_dueno("Jean Carlo", "JeanCarlo", "1234", "1234")
    assert dueno.es_dueno
    assert dueno.usuario == "jeancarlo"
    assert re.fullmatch(r"[A-Z2-9]{4}(-[A-Z2-9]{4}){3}", clave)
    assert clave.replace("-", "") not in dueno.clave_recuperacion  # se guarda solo el hash
    assert dueno.check_password("1234")


def test_solo_un_primer_arranque(dueno):
    with pytest.raises(ReglaNegocio):
        servicios.crear_dueno("Otro", "otro", "1111", "1111")


def test_un_solo_dueno_en_la_base_de_datos(dueno):
    with pytest.raises(IntegrityError), transaction.atomic():
        Usuario.objects.create_user("otro", "Otro", "1111", es_dueno=True)


@pytest.mark.parametrize(
    ("pin", "repetido"), [("123", "123"), ("12345", "12345"), ("abcd", "abcd"), ("1234", "4321")]
)
def test_pin_invalido(db, pin, repetido):
    with pytest.raises(ReglaNegocio):
        servicios.crear_dueno("Jean", "jean", pin, repetido)


@pytest.mark.parametrize("usuario", ["ab", "con espacio", "josé", ""])
def test_usuario_invalido(db, usuario):
    with pytest.raises(ReglaNegocio):
        servicios.crear_dueno("Jean", usuario, "1234", "1234")


# --- Colaboradores y permisos -----------------------------------------------


def test_colaborador_nuevo_recibe_permisos_por_defecto(colaborador):
    assert servicios.permisos_de(colaborador) == set(POR_DEFECTO)
    assert colaborador.tiene_permiso("vender")
    assert not colaborador.tiene_permiso("anular_ventas")


def test_dueno_tiene_todo(dueno):
    assert all(dueno.tiene_permiso(c) for c in CODIGOS)


def test_solo_el_dueno_crea_colaboradores(colaborador):
    with pytest.raises(ReglaNegocio):
        servicios.crear_colaborador(colaborador, "Hermano", "hermano", "1111", "1111")


def test_usuario_repetido(dueno, colaborador):
    with pytest.raises(ReglaNegocio, match="Ya existe"):
        servicios.crear_colaborador(dueno, "Otra", colaborador.usuario, "1111", "1111")


def test_asignar_permisos_aplica_de_inmediato_y_queda_en_bitacora(dueno, colaborador):
    assert not colaborador.tiene_permiso("anular_ventas")
    servicios.asignar_permisos(dueno, colaborador, POR_DEFECTO | {"anular_ventas"})
    assert colaborador.tiene_permiso("anular_ventas")  # mismo objeto, sin recargar
    registro = Bitacora.objects.filter(accion="usuarios.permisos").latest("id")
    assert registro.detalle["activados"] == ["anular_ventas"]
    assert registro.usuario == dueno


def test_permiso_desconocido(dueno, colaborador):
    with pytest.raises(ReglaNegocio):
        servicios.asignar_permisos(dueno, colaborador, {"borrar_todo"})


def test_colaborador_inactivo_no_tiene_permisos(dueno, colaborador):
    servicios.actualizar_colaborador(
        dueno, colaborador, nombre="Esposa", activo=False, permisos=POR_DEFECTO
    )
    assert not colaborador.tiene_permiso("vender")
    with pytest.raises(ReglaNegocio):
        servicios.autenticar(colaborador.usuario, "5678")


# --- Inicio de sesión y bloqueo ---------------------------------------------


def test_autenticar_correcto(dueno):
    assert servicios.autenticar("JeanCarlo", "1234") == dueno


def test_autenticar_usuario_inexistente_mismo_mensaje(db):
    with pytest.raises(ReglaNegocio, match="Usuario o PIN incorrecto"):
        servicios.autenticar("nadie", "1234")


def test_bloqueo_tras_intentos_fallidos(dueno):
    intentos = Configuracion.cargar().intentos_pin
    for _ in range(intentos):
        with pytest.raises(ReglaNegocio):
            servicios.autenticar("jeancarlo", "0000")
    # Bloqueado: ni siquiera el PIN correcto entra.
    with pytest.raises(ReglaNegocio, match="bloqueado"):
        servicios.autenticar("jeancarlo", "1234")
    assert Bitacora.objects.filter(accion="usuarios.bloqueo").exists()


def test_bloqueo_vence(dueno):
    Usuario.objects.filter(pk=dueno.pk).update(
        bloqueado_hasta=timezone.now() - timedelta(seconds=1)
    )
    assert servicios.autenticar("jeancarlo", "1234") == dueno


def test_acierto_limpia_intentos(dueno):
    with pytest.raises(ReglaNegocio):
        servicios.autenticar("jeancarlo", "0000")
    servicios.autenticar("jeancarlo", "1234")
    dueno.refresh_from_db()
    assert dueno.intentos_fallidos == 0


# --- Recuperación -----------------------------------------------------------


def test_recuperar_con_clave_genera_clave_nueva(db):
    _, clave = servicios.crear_dueno("Jean", "jean", "1234", "1234")
    dueno, nueva = servicios.recuperar_con_clave("jean", clave.lower(), "9999", "9999")
    assert dueno.check_password("9999")
    assert nueva != clave
    # La clave anterior ya no sirve.
    with pytest.raises(ReglaNegocio):
        servicios.recuperar_con_clave("jean", clave, "8888", "8888")


def test_clave_incorrecta_cuenta_como_intento(dueno):
    with pytest.raises(ReglaNegocio):
        servicios.recuperar_con_clave("jeancarlo", "AAAA-AAAA-AAAA-AAAA", "9999", "9999")
    dueno.refresh_from_db()
    assert dueno.intentos_fallidos == 1


def test_colaborador_no_usa_clave_de_recuperacion(colaborador):
    with pytest.raises(ReglaNegocio):
        servicios.recuperar_con_clave(colaborador.usuario, "X", "9999", "9999")
