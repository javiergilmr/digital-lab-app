const ACCEPTED_EXTENSIONS = [".csv", ".xlsx"];
const MAX_UPLOAD_MB = 10; // igual que en main.py

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const dropTitle = document.getElementById("dz-title");
const fileLabel = document.getElementById("dz-file");
const progressBar = document.getElementById("dz-bar");
const statusEl = document.getElementById("status");

const errorBox = document.getElementById("upload-error");
const errorMsg = errorBox.querySelector(".upload-error-message");

let uploading = false;

function showUploadError(message) {
  errorMsg.textContent =
    message ||
    "El archivo no pudo ser procesado. Revisa el formato e inténtalo nuevamente.";
  errorBox.classList.remove("hidden");
}

function hideUploadError() {
  errorBox.classList.add("hidden");
}

function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function setProgress(percent, text) {
  progressBar.style.width = `${percent}%`;
  statusEl.textContent = text;
}

function resetDropzone() {
  uploading = false;
  fileInput.value = "";
  dropzone.dataset.state = "idle";
}

/* ======================
   ELEGIR ARCHIVO
   ====================== */
function pickFile(files) {
  if (uploading || !files.length) return;

  if (files.length > 1) {
    showUploadError("Sube un solo archivo a la vez.");
    return;
  }

  const file = files[0];
  const name = file.name.toLowerCase();

  if (!ACCEPTED_EXTENSIONS.some(ext => name.endsWith(ext))) {
    showUploadError("Ese formato no es compatible. Sube un archivo CSV o Excel (.xlsx).");
    return;
  }

  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    showUploadError(`El archivo pesa más de ${MAX_UPLOAD_MB} MB. Sube uno más liviano.`);
    return;
  }

  uploadFile(file);
}

/* ======================
   SUBIR (XMLHttpRequest permite mostrar el progreso real de la subida)
   ====================== */
function sendFile(file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/upload");

    xhr.upload.addEventListener("progress", e => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    });

    xhr.addEventListener("load", () => {
      let data = {};
      try {
        data = JSON.parse(xhr.responseText);
      } catch {}
      resolve({ ok: xhr.status >= 200 && xhr.status < 300, status: xhr.status, data });
    });

    xhr.addEventListener("error", () => reject(new Error("network")));

    const formData = new FormData();
    formData.append("file", file);
    xhr.send(formData);
  });
}

async function uploadFile(file) {
  uploading = true;
  hideUploadError();

  fileLabel.textContent = `${file.name} · ${formatSize(file.size)}`;
  setProgress(0, "Subiendo archivo…");
  dropzone.dataset.state = "uploading";

  try {
    const res = await sendFile(file, fraction => {
      // La subida llena hasta 90%; el resto es la revisión de columnas en el servidor
      if (fraction < 1) {
        setProgress(fraction * 90, `Subiendo archivo… ${Math.round(fraction * 100)}%`);
      } else {
        setProgress(90, "Revisando columnas…");
      }
    });

    /* ❌ ERROR BACKEND */
    if (!res.ok) {
      resetDropzone();
      if (res.status === 401) {
        window.location.href = "/login?next=/";
        return;
      }
      showUploadError(res.data.detail);
      return;
    }

    /* ⚠️ RESPUESTA RARA */
    if (!res.data.session_id) {
      resetDropzone();
      showUploadError("Respuesta inesperada del servidor.");
      return;
    }

    /* ✅ ÉXITO */
    setProgress(100, "✔ Archivo cargado");
    await wait(600);
    window.location.href = `/map/${res.data.session_id}`;

  } catch (err) {
    resetDropzone();
    showUploadError("Error de conexión. Intenta nuevamente.");
  }
}

/* ======================
   DATOS DE EJEMPLO (el servidor carga static/demo_ventas.csv)
   ====================== */
const demoBtn = document.getElementById("demo-btn");

async function loadDemo() {
  if (uploading) return;
  uploading = true;
  demoBtn.disabled = true;
  hideUploadError();

  fileLabel.textContent = "demo_ventas.csv · datos de ejemplo";
  setProgress(40, "Cargando datos de ejemplo…");
  dropzone.dataset.state = "uploading";

  try {
    const res = await fetch("/api/demo", { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.session_id) {
      throw new Error(data.detail || "No se pudieron cargar los datos de ejemplo.");
    }
    setProgress(100, "✔ Datos de ejemplo cargados");
    await wait(500);
    window.location.href = `/map/${data.session_id}`;
  } catch (err) {
    resetDropzone();
    demoBtn.disabled = false;
    showUploadError(err.message === "Failed to fetch" ? "Error de conexión. Intenta nuevamente." : err.message);
  }
}

demoBtn.addEventListener("click", loadDemo);

/* ======================
   CLIC Y BOTÓN (el botón está dentro de la zona: su clic llega aquí)
   ====================== */
dropzone.addEventListener("click", () => {
  if (!uploading) fileInput.click();
});

fileInput.addEventListener("change", () => pickFile(fileInput.files));

/* ======================
   ARRASTRAR Y SOLTAR
   ====================== */
function setDragover(active) {
  dropzone.classList.toggle("is-dragover", active && !uploading);
  dropTitle.textContent = active && !uploading ? "Suelta el archivo aquí" : "Arrastra tu archivo aquí";
}

dropzone.addEventListener("dragenter", e => {
  e.preventDefault();
  setDragover(true);
});

dropzone.addEventListener("dragover", e => {
  e.preventDefault();
  e.dataTransfer.dropEffect = uploading ? "none" : "copy";
  setDragover(true);
});

dropzone.addEventListener("dragleave", e => {
  if (!dropzone.contains(e.relatedTarget)) setDragover(false);
});

dropzone.addEventListener("drop", e => {
  e.preventDefault();
  setDragover(false);
  pickFile(e.dataTransfer.files);
});

// Si el archivo cae fuera de la zona, el navegador no lo abre en la pestaña
window.addEventListener("dragover", e => e.preventDefault());
window.addEventListener("drop", e => e.preventDefault());
