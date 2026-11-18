from django import forms

from apps.nucleo.cantidades import Unidad

from .models import MotivoAjuste


class NuevoProductoForm(forms.Form):
    nombre = forms.CharField(label="Nombre", max_length=120)
    unidad = forms.ChoiceField(
        label="Unidad de medida",
        choices=Unidad.choices,
        initial=Unidad.UNIDAD,
        widget=forms.RadioSelect(attrs={"class": "pildora"}),
    )
    # Texto: se leen en formato colombiano con apps.nucleo.numeros.
    precio = forms.CharField(
        label="Precio de venta ($)", widget=forms.TextInput(attrs={"inputmode": "decimal"})
    )
    cantidad_inicial = forms.CharField(
        label="Cantidad inicial (opcional)",
        required=False,
        widget=forms.TextInput(attrs={"inputmode": "decimal", "placeholder": "0"}),
    )


class CorregirForm(forms.Form):
    nueva_cantidad = forms.CharField(
        label="Nueva cantidad",
        widget=forms.TextInput(attrs={"inputmode": "decimal", "autofocus": True}),
    )
    motivo = forms.ChoiceField(
        label="Motivo",
        choices=MotivoAjuste.choices,
        initial=MotivoAjuste.CONTEO,
        widget=forms.RadioSelect(attrs={"class": "pildora"}),
    )
