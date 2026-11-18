from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Q

from apps.nucleo.permisos import APP_LABEL


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, usuario: str, nombre: str, password: str, **extra) -> "Usuario":
        user = self.model(usuario=usuario, nombre=nombre, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, usuario: str, nombre: str, password: str, **extra) -> "Usuario":
        return self.create_user(usuario, nombre, password, es_dueno=True, **extra)


class Tema(models.TextChoices):
    SISTEMA = "sistema", "Igual que el computador"
    CLARO = "claro", "Claro"
    OSCURO = "oscuro", "Oscuro"


class Usuario(AbstractBaseUser, PermissionsMixin):
    """Persona que entra a la app con su usuario y un PIN de 4 dígitos.

    El PIN se guarda con el sistema de contraseñas de Django (hash con sal).
    El dueño tiene todos los permisos; los colaboradores, los que él active.
    """

    usuario = models.CharField("usuario", max_length=30, unique=True)
    nombre = models.CharField("nombre", max_length=80)
    es_dueno = models.BooleanField("es el dueño", default=False)
    is_active = models.BooleanField("activo", default=True)
    intentos_fallidos = models.PositiveSmallIntegerField(default=0)
    bloqueado_hasta = models.DateTimeField(null=True, blank=True)
    clave_recuperacion = models.CharField(max_length=128, blank=True)
    tema = models.CharField("apariencia", max_length=10, choices=Tema.choices, default=Tema.SISTEMA)
    creado_en = models.DateTimeField(auto_now_add=True)

    objects = UsuarioManager()

    USERNAME_FIELD = "usuario"
    REQUIRED_FIELDS = ["nombre"]

    class Meta:
        ordering = ["-es_dueno", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["es_dueno"],
                condition=Q(es_dueno=True),
                name="usuarios_un_solo_dueno",
            )
        ]

    def __str__(self) -> str:
        return self.nombre

    @property
    def is_staff(self) -> bool:
        # El panel de administración de Django está desactivado: se salta los servicios.
        return False

    @property
    def rol(self) -> str:
        return "Dueño" if self.es_dueno else "Colaborador"

    @property
    def inicial(self) -> str:
        return self.nombre[:1].upper()

    def tiene_permiso(self, codigo: str) -> bool:
        if not self.is_active:
            return False
        if self.es_dueno:
            return True
        return self.has_perm(f"{APP_LABEL}.{codigo}")
