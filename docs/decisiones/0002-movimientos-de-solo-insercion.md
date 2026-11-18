# 0002. Movimientos de solo inserción y saldos derivados

## Contexto

La tienda necesita trazabilidad: saber qué pasó con cada producto y cada deuda.
Un campo de existencia editable permite descuadres que nadie puede explicar.

## Decisión

- Inventario, fiados y bitácora se guardan como movimientos. Un trigger de la
  base de datos rechaza `UPDATE` y `DELETE` sobre esas tablas.
- `Producto.existencia` y `Cliente.saldo` son columnas derivadas que solo
  actualiza el servicio, en la misma transacción que inserta el movimiento.
  Así las pantallas no suman millones de filas.
- `python manage.py verificar_saldos` recalcula y avisa si algo no cuadra.
  Una prueba hace 60 operaciones al azar y comprueba que todo cuadra.

## Consecuencias

- Corregir un error crea un movimiento nuevo; la historia nunca se pierde.
- No se pueden borrar productos, clientes ni usuarios con historia: se
  desactivan.
