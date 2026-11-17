// Tema día / noche. Se carga en <head> (sin defer) para aplicar el tema antes de pintar la página
// y que no haya un destello claro al entrar de noche.
(function () {
  var KEY = "theme";
  var media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  function saved() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }

  function current() {
    return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  }

  function apply(theme) {
    document.documentElement.dataset.theme = theme;
    var label = theme === "dark" ? "Cambiar a modo día" : "Cambiar a modo noche";
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      btn.setAttribute("aria-label", label);
      btn.title = label;
    });
    // Para quien dibuja con colores del tema (ej. el gráfico del informe)
    document.dispatchEvent(new CustomEvent("themechange", { detail: { theme: theme } }));
  }

  // Sin elección guardada, sigue al sistema (también si cambia mientras la página está abierta)
  apply(saved() || (media && media.matches ? "dark" : "light"));
  if (media && media.addEventListener) {
    media.addEventListener("change", function (e) {
      if (!saved()) apply(e.matches ? "dark" : "light");
    });
  }

  document.addEventListener("DOMContentLoaded", function () { apply(current()); });

  document.addEventListener("click", function (e) {
    var btn = e.target.closest && e.target.closest("[data-theme-toggle]");
    if (!btn) return;
    var next = current() === "dark" ? "light" : "dark";
    try { localStorage.setItem(KEY, next); } catch (err) {}
    apply(next);
  });
})();
