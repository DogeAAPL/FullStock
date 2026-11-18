from django.db import migrations

from apps.nucleo.sql import solo_insercion


class Migration(migrations.Migration):
    """La tabla fiados_movimientofiado solo admite INSERT: la historia no se edita ni se borra."""

    dependencies = [("fiados", "0002_initial")]

    operations = [solo_insercion("fiados_movimientofiado")]
