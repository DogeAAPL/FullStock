"""Operaciones de migración que protegen la historia en la base de datos misma.

Una tabla de solo inserción rechaza UPDATE y DELETE con un trigger. Así ni un
error de código ni un script pueden alterar movimientos ya registrados: lo que
estuvo mal se corrige con un movimiento nuevo.

Hay una versión para SQLite (la tienda) y otra para PostgreSQL (si algún día
se publica en un servidor).
"""

from django.db import migrations

_FUNCION_PG = """
CREATE OR REPLACE FUNCTION fullstock_solo_insercion() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'La tabla % es de solo inserción', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;
"""


def solo_insercion(tabla: str) -> migrations.RunPython:
    def crear(apps, schema_editor):
        vendor = schema_editor.connection.vendor
        if vendor == "sqlite":
            for evento in ("UPDATE", "DELETE"):
                schema_editor.execute(
                    f"CREATE TRIGGER {tabla}_no_{evento.lower()} BEFORE {evento} ON {tabla} "
                    f"BEGIN SELECT RAISE(ABORT, 'La tabla {tabla} es de solo inserción'); END;"
                )
        elif vendor == "postgresql":
            schema_editor.execute(_FUNCION_PG)
            schema_editor.execute(
                f"CREATE TRIGGER {tabla}_solo_insercion BEFORE UPDATE OR DELETE ON {tabla} "
                "FOR EACH ROW EXECUTE FUNCTION fullstock_solo_insercion();"
            )
        else:
            raise NotImplementedError(f"Base de datos no soportada: {vendor}")

    def eliminar(apps, schema_editor):
        vendor = schema_editor.connection.vendor
        if vendor == "sqlite":
            for evento in ("update", "delete"):
                schema_editor.execute(f"DROP TRIGGER IF EXISTS {tabla}_no_{evento};")
        elif vendor == "postgresql":
            schema_editor.execute(f"DROP TRIGGER IF EXISTS {tabla}_solo_insercion ON {tabla};")

    return migrations.RunPython(crear, eliminar)
