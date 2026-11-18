# 0001. Página web que corre en el computador de la tienda

## Contexto

El cliente pide una página web, sin PWA y sin versión móvil. La tienda debe
poder vender aunque se caiga internet.

## Decisión

Django + HTMX + SQLite, servidos por Waitress en `127.0.0.1` del computador
de la tienda (Windows 10 u 11). Se usa desde el navegador.

## Consecuencias

- Funciona sin internet y no hay costos de servidor.
- Nadie fuera del computador puede abrirla; el PIN de 4 dígitos es suficiente
  con bloqueo por intentos.
- El mismo código puede publicarse en un servidor después: la configuración va
  por variables de entorno y los triggers tienen versión para PostgreSQL. Si se
  publica en internet, el PIN de 4 dígitos ya no basta.
- Los respaldos son responsabilidad de la app (pendiente).
