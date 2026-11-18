"""Configuración de FullStock.

Todo lo que cambia entre la tienda y un servidor se lee de variables de
entorno con prefijo FULLSTOCK_ (y DATABASE_URL). Hay dos formas de correr:

- En el computador de la tienda: SQLite en RUTA_DATOS, solo en 127.0.0.1.
- Como página web pública (Render): PostgreSQL por DATABASE_URL y HTTPS.
"""

import os
from pathlib import Path

import dj_database_url
from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent


def _env(nombre: str, defecto: str = "") -> str:
    return os.environ.get(f"FULLSTOCK_{nombre}", defecto)


RUTA_DATOS = Path(_env("DATA_DIR", str(BASE_DIR / "datos")))
RUTA_DATOS.mkdir(parents=True, exist_ok=True)

DEBUG = _env("DEBUG", "0") == "1"

# Nombre que se muestra en el menú lateral.
TIENDA_NOMBRE = _env("TIENDA_NOMBRE", "El Papayal")

# Modo demostración: la pantalla de entrada muestra usuarios y PIN de prueba.
DEMO = _env("DEMO", "0") == "1"


def _clave_secreta() -> str:
    """Una clave por instalación, generada la primera vez y nunca versionada."""
    if valor := _env("SECRET_KEY"):
        return valor
    archivo = RUTA_DATOS / "clave_secreta.txt"
    if not archivo.exists():
        archivo.write_text(get_random_secret_key(), encoding="utf-8")
    return archivo.read_text(encoding="utf-8").strip()


SECRET_KEY = _clave_secreta()

# En la tienda solo se escucha en el propio computador (ver docs/decisiones).
ALLOWED_HOSTS = [h for h in _env("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in _env("CSRF_TRUSTED_ORIGINS").split(",") if o]

# Render publica el dominio del servicio en esta variable.
if dominio := os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(dominio)
    CSRF_TRUSTED_ORIGINS.append(f"https://{dominio}")

# Detrás de un proxy con HTTPS (Render): cookies solo por HTTPS. La redirección
# de http a https la hace Render antes de llegar a la app.
if _env("HTTPS", "0") == "1" or os.environ.get("RENDER"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.nucleo",
    "apps.usuarios",
    "apps.catalogo",
    "apps.inventario",
    "apps.fiados",
    "apps.ventas",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.nucleo.middleware.ConfiguracionMiddleware",
    "apps.nucleo.middleware.PrimerArranqueMiddleware",
    "apps.nucleo.middleware.InactividadMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.nucleo.context_processors.navegacion",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# SQLite configurado para uso real (ver documento de rendimiento):
# WAL para leer mientras se escribe, IMMEDIATE para evitar "database is locked"
# a mitad de una venta y synchronous=FULL para no perder la última venta si se
# va la luz. Con DATABASE_URL se usa esa base (PostgreSQL en el servidor).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": RUTA_DATOS / "fullstock.sqlite3",
        "OPTIONS": {
            "transaction_mode": "IMMEDIATE",
            "timeout": 10,
            "init_command": (
                "PRAGMA journal_mode=WAL;"
                "PRAGMA synchronous=FULL;"
                "PRAGMA temp_store=MEMORY;"
                "PRAGMA cache_size=-20000;"
            ),
        },
    }
}

if url_base := os.environ.get("DATABASE_URL"):
    DATABASES["default"] = dj_database_url.parse(url_base, conn_max_age=60, conn_health_checks=True)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "usuarios.Usuario"
# El PIN se valida en el servicio de usuarios (exactamente 4 dígitos).
AUTH_PASSWORD_VALIDATORS: list[dict] = []
LOGIN_URL = "usuarios:login"
LOGIN_REDIRECT_URL = "inicio"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

RUTA_REGISTROS = RUTA_DATOS / "registros"
RUTA_REGISTROS.mkdir(exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {
        "archivo": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": RUTA_REGISTROS / "fullstock.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "simple",
        },
        "consola": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["archivo", "consola"], "level": "INFO"},
}
