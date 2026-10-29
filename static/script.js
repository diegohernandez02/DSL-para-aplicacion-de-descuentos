// Comportamiento de la interfaz (frontend). El análisis léxico ocurre en el servidor (Flask).
(function () {
  "use strict";

  var codigo = document.getElementById("codigo");
  var archivo = document.getElementById("archivo");
  var nombre = document.getElementById("nombre-archivo");
  var btnEjemplo = document.getElementById("btn-ejemplo");
  var btnLimpiar = document.getElementById("btn-limpiar");
  if (!codigo) { return; }

  if (btnEjemplo) {
    btnEjemplo.addEventListener("click", function () {
      codigo.value = codigo.dataset.ejemplo || "";
      codigo.focus();
    });
  }

  if (btnLimpiar) {
    btnLimpiar.addEventListener("click", function () {
      codigo.value = "";
      if (archivo) { archivo.value = ""; }
      if (nombre) { nombre.textContent = ""; }
      codigo.focus();
    });
  }

  if (archivo && nombre) {
    archivo.addEventListener("change", function () {
      nombre.textContent = archivo.files.length
        ? "Se analizará el archivo: " + archivo.files[0].name
        : "";
    });
  }
})();
