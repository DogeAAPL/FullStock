from django import forms

from apps.nucleo.fechas import hoy

_NUM = {"inputmode": "decimal", "autocomplete": "off"}


class ProveedorForm(forms.Form):
    nombre = forms.CharField(label="Nombre", max_length=120)
    telefono = forms.CharField(label="Teléfono (opcional)", max_length=30, required=False)


class PedidoForm(forms.Form):
    producto_id = forms.IntegerField(widget=forms.HiddenInput)
    cantidad = forms.CharField(label="Cantidad", widget=forms.TextInput(attrs=_NUM))
    costo_unitario = forms.CharField(label="Costo unitario ($)", widget=forms.TextInput(attrs=_NUM))
    proveedor_id = forms.TypedChoiceField(label="Proveedor", coerce=int)
    fecha_pedido = forms.DateField(
        label="Fecha del pedido", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )

    def __init__(self, *args, proveedores=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["proveedor_id"].choices = [
            ("", "Elige…"),
            *[(p.pk, p.nombre) for p in proveedores],
        ]
        self.fields["fecha_pedido"].widget.attrs["max"] = hoy().isoformat()


class RecibirForm(forms.Form):
    cantidad_recibida = forms.CharField(
        label="Cantidad recibida", widget=forms.TextInput(attrs=_NUM)
    )
    costo_unitario = forms.CharField(label="Costo unitario ($)", widget=forms.TextInput(attrs=_NUM))
    fecha_llegada = forms.DateField(
        label="Fecha de llegada", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
