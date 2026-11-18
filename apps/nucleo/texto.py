import unicodedata


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con espacios simples. Sirve para buscar y comparar nombres."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return " ".join(sin_tildes.lower().split())
