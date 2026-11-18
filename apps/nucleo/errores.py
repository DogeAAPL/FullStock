class ReglaNegocio(Exception):
    """Error esperado de una regla del negocio, con un mensaje para mostrar al usuario.

    Los servicios la lanzan; las vistas la capturan y muestran `str(error)`.
    """
