from django import forms

from apps.nucleo.models import Configuracion
from apps.nucleo.permisos import CATALOGO

_PIN_ATTRS = {
    "inputmode": "numeric",
    "pattern": r"\d{4}",
    "maxlength": "4",
    "autocomplete": "off",
    "class": "campo-pin",
}


def _pin(label: str, requerido: bool = True) -> forms.CharField:
    return forms.CharField(
        label=label,
        required=requerido,
        widget=forms.PasswordInput(attrs=_PIN_ATTRS),
    )


class PrimerArranqueForm(forms.Form):
    nombre = forms.CharField(label="Nombre", max_length=80)
    usuario = forms.CharField(
        label="Usuario", max_length=30, widget=forms.TextInput(attrs={"autocapitalize": "none"})
    )
    pin = _pin("PIN de 4 dígitos")
    pin_repetido = _pin("Repite el PIN")


class LoginForm(forms.Form):
    usuario = forms.CharField(
        label="Usuario",
        max_length=30,
        widget=forms.TextInput(attrs={"autofocus": True, "autocapitalize": "none"}),
    )
    pin = _pin("PIN")


class RecuperarForm(forms.Form):
    usuario = forms.CharField(label="Usuario del dueño", max_length=30)
    clave = forms.CharField(
        label="Clave de recuperación",
        widget=forms.TextInput(attrs={"placeholder": "XXXX-XXXX-XXXX-XXXX", "autocomplete": "off"}),
    )
    pin = _pin("PIN nuevo")
    pin_repetido = _pin("Repite el PIN nuevo")


def _opciones_permisos():
    return [(p.codigo, p.nombre) for p in CATALOGO]


class ColaboradorForm(forms.Form):
    nombre = forms.CharField(label="Nombre", max_length=80)
    usuario = forms.CharField(
        label="Usuario",
        max_length=30,
        help_text="Va sin espacios ni tildes. Con él entra a la app.",
        widget=forms.TextInput(attrs={"autocapitalize": "none"}),
    )
    pin = _pin("PIN de 4 dígitos")
    pin_repetido = _pin("Repite el PIN")
    permisos = forms.MultipleChoiceField(
        label="Qué podrá hacer",
        choices=_opciones_permisos,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "interruptor"}),
    )


class EditarColaboradorForm(forms.Form):
    nombre = forms.CharField(label="Nombre", max_length=80)
    activo = forms.BooleanField(label="Puede entrar a la app", required=False)
    pin = _pin("PIN nuevo (opcional)", requerido=False)
    pin_repetido = _pin("Repite el PIN nuevo", requerido=False)
    permisos = forms.MultipleChoiceField(
        label="Qué puede hacer",
        choices=_opciones_permisos,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "interruptor"}),
    )


class ConfiguracionForm(forms.ModelForm):
    class Meta:
        model = Configuracion
        fields = [
            "minutos_inactividad",
            "intentos_pin",
            "minutos_bloqueo",
            "vender_sin_existencia",
            "limite_deuda",
            "horas_respaldo",
            "carpeta_usb",
        ]
