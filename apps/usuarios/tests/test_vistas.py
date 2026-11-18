import time

import pytest
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from apps.nucleo.permisos import CODIGOS
from apps.usuarios.models import Usuario


def test_sin_usuarios_todo_lleva_al_primer_arranque(client, db):
    respuesta = client.get(reverse("inventario:lista"))
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("usuarios:primer_arranque")


def test_primer_arranque_crea_dueno_y_muestra_clave_una_vez(client, db):
    respuesta = client.post(
        reverse("usuarios:primer_arranque"),
        {"nombre": "Jean Carlo", "usuario": "jeancarlo", "pin": "1234", "pin_repetido": "1234"},
    )
    assert respuesta.url == reverse("usuarios:clave")
    pagina = client.get(reverse("usuarios:clave"))
    assert "Guarda esta clave" in pagina.content.decode()
    # La segunda vez ya no se muestra.
    assert client.get(reverse("usuarios:clave")).status_code == 302
    assert Usuario.objects.get().es_dueno


def test_login_y_redireccion(client, dueno):
    respuesta = client.post(reverse("usuarios:login"), {"usuario": "jeancarlo", "pin": "1234"})
    assert respuesta.status_code == 302
    assert client.get(reverse("inicio")).url == reverse("ventas:vender")


def test_login_no_redirige_fuera_del_sitio(client, dueno):
    respuesta = client.post(
        reverse("usuarios:login") + "?next=https://otro.sitio/",
        {"usuario": "jeancarlo", "pin": "1234"},
    )
    assert respuesta.url == reverse("inicio")


def test_login_fallido_muestra_error(client, dueno):
    respuesta = client.post(reverse("usuarios:login"), {"usuario": "jeancarlo", "pin": "0000"})
    assert respuesta.status_code == 200
    assert "Usuario o PIN incorrecto" in respuesta.content.decode()


def test_sesion_se_cierra_por_inactividad(cliente_web, dueno):
    web = cliente_web(dueno)
    assert web.get(reverse("inventario:lista")).status_code == 200
    sesion = web.session
    sesion["ultima_actividad"] = time.time() - 11 * 60  # 10 min por defecto
    sesion.save()
    respuesta = web.get(reverse("inventario:lista"))
    assert respuesta.status_code == 302
    assert reverse("usuarios:login") in respuesta.url


def test_inactividad_con_htmx_redirige_por_cabecera(cliente_web, dueno):
    web = cliente_web(dueno)
    web.get(reverse("inventario:lista"))
    sesion = web.session
    sesion["ultima_actividad"] = time.time() - 11 * 60
    sesion.save()
    respuesta = web.get(reverse("inventario:lista"), headers={"HX-Request": "true"})
    assert respuesta["HX-Redirect"] == reverse("usuarios:login")


# --- Matriz de permisos -----------------------------------------------------
# Recorre todas las vistas del proyecto y comprueba que cada una exija en el
# servidor el permiso que declara. Una vista nueva sin permiso hace fallar la prueba.

_PUBLICAS = {
    "usuarios:primer_arranque",
    "usuarios:clave",
    "usuarios:login",
    "usuarios:logout",
    "usuarios:recuperar",
    "inicio",
}


def _vistas():
    def recorrer(patrones, prefijo=""):
        for p in patrones:
            if isinstance(p, URLResolver):
                yield from recorrer(p.url_patterns, f"{p.namespace}:" if p.namespace else prefijo)
            elif isinstance(p, URLPattern):
                yield f"{prefijo}{p.name}", p

    return list(recorrer(get_resolver().url_patterns))


def _url(nombre: str, patron: URLPattern) -> str:
    argumentos = {k: 1 for k in patron.pattern.converters}
    return reverse(nombre, kwargs=argumentos)


def test_toda_vista_privada_declara_su_permiso():
    sin_permiso = [
        nombre
        for nombre, patron in _vistas()
        if nombre not in _PUBLICAS and not hasattr(patron.callback, "permiso_requerido")
    ]
    assert sin_permiso == []


@pytest.mark.parametrize("nombre", [n for n, p in _vistas() if n not in _PUBLICAS], ids=lambda n: n)
def test_vista_rechaza_a_quien_no_tiene_el_permiso(nombre, crear_colaborador, cliente_web):
    patron = dict(_vistas())[nombre]
    requerido = patron.callback.permiso_requerido
    # Colaborador con TODOS los permisos menos el requerido.
    colaborador = crear_colaborador(permisos=CODIGOS - {requerido})
    respuesta = cliente_web(colaborador).get(_url(nombre, patron))
    assert respuesta.status_code == 403


@pytest.mark.parametrize(
    "nombre",
    [
        n
        for n, p in _vistas()
        if n not in _PUBLICAS and p.callback.permiso_requerido != "solo_dueno"
    ],
    ids=lambda n: n,
)
def test_vista_permite_a_quien_tiene_el_permiso(nombre, crear_colaborador, cliente_web):
    patron = dict(_vistas())[nombre]
    colaborador = crear_colaborador(permisos={patron.callback.permiso_requerido})
    respuesta = cliente_web(colaborador).get(_url(nombre, patron))
    # 404/405 son válidos (objeto inexistente o vista solo POST): lo que importa es que no sea 403.
    assert respuesta.status_code != 403
