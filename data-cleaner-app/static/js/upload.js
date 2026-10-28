const form = document.getElementById("upload-form");
const statusEl = document.getElementById("status");

const errorBox = document.getElementById("upload-error");
const errorMsg = errorBox.querySelector(".upload-error-message");

function showUploadError(message) {
  errorMsg.textContent =
    message ||
    "El archivo no pudo ser procesado. Revisa el formato e inténtalo nuevamente.";

  errorBox.style.opacity = "1";
  errorBox.classList.remove("hidden");

  requestAnimationFrame(() => {
    errorBox.style.opacity = "1";
  });
}

function hideUploadError() {
  errorBox.classList.add("hidden");
  errorBox.style.opacity = "0";
}

function showStatus(text) {
  statusEl.textContent = text;
  statusEl.style.opacity = "1";
}

function hideStatus() {
  statusEl.style.opacity = "0";
}

function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  // reset visual
  hideUploadError();
  showStatus("Subiendo archivo…");

  const formData = new FormData(form);

  try {
    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData,
    });

    const data = await res.json();

    /* ======================
       ❌ ERROR BACKEND
       ====================== */
    if (!res.ok) {
      await wait(100);
      hideStatus();
      showUploadError(data.detail);
      return;
    }

    /* ======================
       ✅ ÉXITO
       ====================== */
    if (data.session_id) {
      showStatus("Procesando archivo…");
      await wait(600);

      showStatus("✔ Archivo cargado");
      await wait(400);

      hideStatus();
      await wait(200);

      window.location.href = `/map/${data.session_id}`;
      return;
    }

    /* ======================
       ⚠️ RESPUESTA RARA
       ====================== */
    hideStatus();
    showUploadError("Respuesta inesperada del servidor.");

  } catch (err) {
    hideStatus();
    showUploadError("Error de conexión. Intenta nuevamente.");
  }
});
