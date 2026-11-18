from django.db import migrations


def crear(apps, schema_editor):
    apps.get_model("nucleo", "Configuracion").objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    """Crea la fila de configuración con los valores por defecto."""

    dependencies = [("nucleo", "0003_bitacora_solo_insercion")]

    operations = [migrations.RunPython(crear, migrations.RunPython.noop)]
