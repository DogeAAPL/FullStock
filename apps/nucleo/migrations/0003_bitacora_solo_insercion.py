from django.db import migrations

from apps.nucleo.sql import solo_insercion


class Migration(migrations.Migration):
    """La tabla nucleo_bitacora solo admite INSERT: la historia no se edita ni se borra."""

    dependencies = [("nucleo", "0002_initial")]

    operations = [solo_insercion("nucleo_bitacora")]
