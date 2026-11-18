from django.db import migrations

from apps.nucleo.sql import solo_insercion


class Migration(migrations.Migration):
    """La tabla inventario_movimientoinventario solo admite INSERT: la historia no se edita ni se borra."""

    dependencies = [("inventario", "0002_initial")]

    operations = [solo_insercion("inventario_movimientoinventario")]
