import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import Workbook, load_workbook

from apps.catalogo.models import Producto
from apps.inventario import carga
from apps.nucleo.errores import ReglaNegocio


def _xlsx(filas) -> SimpleUploadedFile:
    libro = Workbook()
    for fila in filas:
        libro.active.append(fila)
    salida = io.BytesIO()
    libro.save(salida)
    return SimpleUploadedFile("productos.xlsx", salida.getvalue())


def test_revision_clasifica_las_filas(tomate):
    archivo = _xlsx(
        [
            ["Nombre", "Unidad", "Precio", "Cantidad"],
            ["Arroz 500 g", "unidad", 2500, 40],
            ["Tomate", "kg", 3000, ""],  # se parece a «Tomate chonto»
            ["", "kg", 1000, ""],  # falta el nombre
            ["Leche", "litro", 4200, ""],  # unidad no válida
            ["Panela", "Libra", "2.400", "1,5"],
            ["Arroz 500 g", "unidad", 2500, 1],  # repetido en el archivo
            ["Huevos", "und", 600, "1,5"],  # unidades enteras
        ]
    )
    revision = carga.revisar(archivo)
    assert [f.nombre for f in revision.crear] == ["Arroz 500 g", "Panela"]
    assert [f.fila for f in revision.existentes] == [3, 7]
    assert [f.fila for f in revision.errores] == [4, 5, 8]
    assert revision.crear[1].precio == 2400


def test_csv_con_punto_y_coma_y_tildes(db):
    contenido = "nombre;unidad;precio\nAtún lata;und;4.500\n".encode("cp1252")
    revision = carga.revisar(SimpleUploadedFile("lista.csv", contenido))
    assert revision.crear[0].nombre == "Atún lata"
    assert revision.crear[0].precio == 4500


@pytest.mark.parametrize(
    ("nombre", "contenido", "mensaje"),
    [
        ("lista.txt", b"x", "xlsx o .csv"),
        ("lista.csv", b"producto;precio\nA;1\n", "columnas"),
    ],
)
def test_archivos_invalidos(db, nombre, contenido, mensaje):
    with pytest.raises(ReglaNegocio, match=mensaje):
        carga.revisar(SimpleUploadedFile(nombre, contenido))


def test_flujo_completo(cliente_web, dueno):
    web = cliente_web(dueno)
    archivo = _xlsx([["nombre", "unidad", "precio", "cantidad"], ["Arroz", "und", 2500, 40]])
    pagina = web.post(reverse("inventario:cargar"), {"archivo": archivo}).content.decode()
    assert "Cargar 1 producto" in pagina
    assert not Producto.objects.exists()  # revisar no crea nada
    web.post(reverse("inventario:cargar"), {"confirmar": "1"})
    arroz = Producto.objects.get(nombre="Arroz")
    assert arroz.existencia == 40


def test_formato_de_ejemplo_es_valido(cliente_web, dueno):
    respuesta = cliente_web(dueno).get(reverse("inventario:formato"))
    libro = load_workbook(io.BytesIO(respuesta.content))
    assert [c.value for c in libro.active[1]] == ["nombre", "unidad", "precio", "cantidad"]
    # El propio formato de ejemplo pasa la revisión.
    revision = carga.revisar(SimpleUploadedFile("formato.xlsx", respuesta.content))
    assert len(revision.crear) == 3 and not revision.errores
