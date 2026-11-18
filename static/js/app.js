// Comportamiento común. Sin dependencias además de HTMX.
(function () {
  "use strict";

  // --- Modal ---------------------------------------------------------------
  // Las vistas devuelven el contenido del modal en #modal-contenido; aquí se abre.
  const modal = document.getElementById("modal");
  if (modal) {
    document.body.addEventListener("htmx:afterSwap", function (evento) {
      if (evento.detail.target.id === "modal-contenido" && !modal.open) {
        modal.showModal();
      }
    });
    modal.addEventListener("click", function (evento) {
      if (evento.target.closest("[data-cerrar-modal]") || evento.target === modal) {
        modal.close();
      }
    });
  }

  // --- Errores de red o del servidor -------------------------------------
  document.body.addEventListener("htmx:responseError", function () {
    window.alert("No se pudo completar la acción. Intenta de nuevo.");
  });
  document.body.addEventListener("htmx:sendError", function () {
    window.alert("No hay conexión con FullStock. ¿Está abierto el programa?");
  });

  // --- Bloqueo por inactividad -------------------------------------------
  // El servidor cierra la sesión tras N minutos sin peticiones. Al cumplirse
  // ese tiempo se recarga la página, y la recarga lleva a la pantalla de entrada.
  const minutos = Number(document.body.dataset.minutosInactividad || 0);
  if (minutos > 0) {
    let temporizador;
    const reiniciar = function () {
      clearTimeout(temporizador);
      temporizador = setTimeout(function () { window.location.reload(); }, minutos * 60000 + 5000);
    };
    document.body.addEventListener("htmx:afterRequest", reiniciar);
    reiniciar();
  }

  // --- Mostrar el bloque de cliente cuando la venta es fiada -------------
  document.body.addEventListener("change", function (evento) {
    if (evento.target.matches("[data-alterna]")) {
      const destino = document.getElementById(evento.target.dataset.alterna);
      if (destino) destino.classList.toggle("oculto", !evento.target.checked);
    }
  });
})();
