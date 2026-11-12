// Ojo para mostrar u ocultar la contraseña en cualquier input[type=password] de la página
const EYE_ICON = `
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>`;

const EYE_OFF_ICON = `
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M10.6 5.1A10.4 10.4 0 0 1 12 5c6.5 0 10 7 10 7a17.6 17.6 0 0 1-2.6 3.6M6.6 6.6A17.4 17.4 0 0 0 2 12s3.5 7 10 7a9.7 9.7 0 0 0 5.4-1.6"/>
    <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>
    <path d="m2 2 20 20"/>
  </svg>`;

document.querySelectorAll('input[type="password"]').forEach(input => {
  const wrap = document.createElement("div");
  wrap.className = "password-wrap";
  input.parentNode.insertBefore(wrap, input);
  wrap.append(input);

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "password-toggle";
  wrap.append(toggle);

  function update() {
    const visible = input.type === "text";
    const label = visible ? "Ocultar contraseña" : "Mostrar contraseña";
    toggle.innerHTML = visible ? EYE_OFF_ICON : EYE_ICON;
    toggle.setAttribute("aria-label", label);
    toggle.setAttribute("aria-pressed", String(visible));
    toggle.title = label;
  }

  // Con el mouse el cursor se queda en el campo; con teclado el botón funciona con Enter o Espacio
  toggle.addEventListener("mousedown", e => e.preventDefault());
  toggle.addEventListener("click", () => {
    input.type = input.type === "password" ? "text" : "password";
    update();
  });

  // Al enviar se vuelve a ocultar, para que el navegador la trate como contraseña al guardarla
  input.form.addEventListener("submit", () => {
    input.type = "password";
    update();
  });

  update();
});
