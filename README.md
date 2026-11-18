# FullStock

Inventario, ventas y fiados para una tienda de barrio. Es una página web que
corre en el computador de la tienda: se abre en el navegador y funciona sin
internet.

## Requisitos

- Windows 10 u 11 (para desarrollar también sirve Linux o macOS)
- Python 3.13
- [uv](https://docs.astral.sh/uv/) para instalar dependencias

## Puesta en marcha para desarrollar

```bash
uv sync                     # crea el entorno e instala versiones exactas (uv.lock)
uv run pre-commit install   # revisa estilo antes de cada commit
```

Servidor de desarrollo (recarga al guardar cambios):

```bash
# Linux / macOS
FULLSTOCK_DEBUG=1 uv run python manage.py migrate
FULLSTOCK_DEBUG=1 uv run python manage.py runserver

# Windows (PowerShell)
$env:FULLSTOCK_DEBUG="1"; uv run python manage.py migrate
$env:FULLSTOCK_DEBUG="1"; uv run python manage.py runserver
```

Abre http://127.0.0.1:8000. La primera vez pide crear el usuario del dueño.

## Como se ejecuta en la tienda

```bash
uv run python manage.py collectstatic --noinput
uv run python manage.py servir          # migra y sirve en http://127.0.0.1:8000
```

`servir` usa Waitress y solo escucha en el propio computador.

## Pruebas y calidad

```bash
uv run pytest          # pruebas
uv run ruff check .    # errores y estilo
uv run ruff format .   # formato
uv run python manage.py verificar_saldos   # existencias contra movimientos
```

## Variables de entorno

| Variable | Para qué | Por defecto |
| --- | --- | --- |
| `FULLSTOCK_DATA_DIR` | Carpeta de la base de datos, clave secreta y registros | `./datos` |
| `FULLSTOCK_DEBUG` | `1` solo para desarrollar | `0` |
| `FULLSTOCK_TIENDA_NOMBRE` | Nombre del negocio, bajo el logo (opcional) | vacío |
| `FULLSTOCK_SECRET_KEY` | Clave secreta; si no está, se genera una por instalación | generada |
| `FULLSTOCK_ALLOWED_HOSTS` | Hosts permitidos, separados por coma | `127.0.0.1,localhost` |

## Estructura

| App | Responsabilidad |
| --- | --- |
| `nucleo` | Dinero, cantidades, fechas, permisos, bitácora, configuración del dueño |
| `usuarios` | Usuarios, PIN, bloqueo, clave de recuperación, panel de permisos |
| `catalogo` | Productos |
| `inventario` | Movimientos, existencias, correcciones |
| `fiados` | Clientes, deudas, abonos y lista de cobros |
| `ventas` | Vender, ventas de hoy, anular y corregir |
| `pedidos` | Proveedores, pedidos, recepción y cancelación |
| `reportes` | Cierre del día y estadísticas |

## Reglas que no se rompen

1. **Las existencias y los saldos son la suma de movimientos.** Las tablas de
   movimientos y la bitácora son de solo inserción: un trigger en la base de
   datos rechaza `UPDATE` y `DELETE`. Un error se corrige con otro movimiento.
2. **Toda escritura pasa por los servicios** (`servicios.py` de cada app). Las
   vistas solo leen el formulario y llaman al servicio. Una app nunca escribe en
   las tablas de otra.
3. **Sin `float` para dinero ni cantidades.** Dinero en pesos enteros; cantidades
   en unidades o gramos (la libra es 500 g). Los números se leen en formato
   colombiano con `nucleo.numeros.leer_numero`.
4. **Los permisos se revisan en el servidor**, con `@requiere_permiso` o
   `@solo_dueno`. Una prueba recorre todas las vistas y falla si alguna no
   declara su permiso.
5. **Una venta no se edita.** Se anula, y "corregir" anula la original y crea una
   nueva enlazada.

Las decisiones y sus razones están en `docs/decisiones/`.

## Versión web de demostración

`render.yaml` publica la app en Render con PostgreSQL. Con `FULLSTOCK_DEMO=1`
la entrada muestra usuarios de prueba y `python manage.py cargar_demo` carga
datos de ejemplo (solo lo que falte). La base gratuita de Render vence a los
30 días.

## Pendiente

Respaldo automático a USB y el instalador para Windows (versión de la tienda).
