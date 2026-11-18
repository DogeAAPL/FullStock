"""El "día de la tienda" se calcula siempre en hora de Colombia.

La base de datos guarda en UTC; una venta de las 7:00 p. m. ya es del día
siguiente en UTC. Toda consulta por día debe usar `rango_dia`.
"""

from datetime import date, datetime, time, timedelta

from django.utils import timezone


def hoy() -> date:
    return timezone.localdate()


def rango_dia(dia: date) -> tuple[datetime, datetime]:
    """Inicio (incluido) y fin (excluido) del día en la zona horaria de la tienda."""
    zona = timezone.get_current_timezone()
    inicio = datetime.combine(dia, time.min, tzinfo=zona)
    return inicio, inicio + timedelta(days=1)
