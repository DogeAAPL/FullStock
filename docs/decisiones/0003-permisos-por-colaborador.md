# 0003. Permisos por colaborador y configuración del dueño

## Contexto

El cliente quiere que el dueño active o desactive funciones para cada
colaborador, y que ajuste reglas como el tiempo de inactividad.

## Decisión

- Un único catálogo de permisos en `apps/nucleo/permisos.py`, guardado con los
  permisos por usuario de Django (sin sistema propio de roles).
- Funciones no delegables (usuarios, permisos, configuración, restaurar
  respaldos): solo el dueño, con `@solo_dueno`.
- Ajustes del dueño en una tabla de configuración de una fila, con límites en
  el formulario y en la base de datos para que no se pueda dejar la app
  insegura por accidente.
- Cada cambio de permisos o configuración queda en la bitácora.

## Consecuencias

- Agregar una función delegable es agregar una línea al catálogo y decorar la
  vista; la prueba de la matriz de permisos la cubre sola.
- El dueño siempre tiene todo y no se puede desactivar.
