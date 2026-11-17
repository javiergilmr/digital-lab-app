# Digital Lab

Proyectos de **Data & Analytics** de Javier Gil Moreno: aplicaciones que convierten datos desordenados en información útil para tomar decisiones.

| Proyecto | Descripción | Tecnologías |
|---|---|---|
| [Data Cleaner & Sales Report](data-cleaner-app/) | Limpia archivos de ventas en CSV o Excel y genera un informe con utilidad, márgenes y desgloses, descargable en PDF | Python · FastAPI · pandas · Supabase |

---

## Data Cleaner & Sales Report

Subes un archivo de ventas con errores y la app lo deja listo para analizar: corrige formatos, quita duplicados, completa precios que faltan y explica cada cambio. Después genera un informe de ventas que se puede descargar.

<!-- Captura de pantalla: guarda la imagen en docs/ y descomenta la línea siguiente -->
<!-- ![Informe de ventas](docs/informe.png) -->

### Qué hace

- **Detecta las columnas solo**: reconoce fecha, producto, cantidad, precio y campos opcionales aunque tengan otros nombres, y deja corregir el mapeo antes de procesar.
- **Limpia los datos**: espacios de sobra, mayúsculas y tildes inconsistentes, precios con `$` o coma decimal, precios negativos o vacíos, fechas inválidas, filas vacías o duplicadas y totales que no cuadran.
- **Genera el informe**: ventas, utilidad, márgenes, desgloses por producto, categoría, tienda y mes, e insights escritos.
- **Permite descargar** los datos limpios en CSV y el informe en PDF.
- **Login opcional** con Supabase (correo y contraseña, o Google). Con cuenta se guardan los stats y el historial de informes en *Mi panel*.
- **Datos de ejemplo**: un año de ventas de 4 tiendas con errores puestos a propósito, para probar la app sin tener un archivo propio.

### Flujo

```
Subir archivo  →  Mapear columnas  →  Procesar  →  Informe + descargas
```

### Stack

| Capa | Tecnología |
|---|---|
| Backend | FastAPI, uvicorn |
| Datos | pandas, numpy, openpyxl |
| Informes | reportlab (PDF) |
| Frontend | Jinja2, HTML, CSS y JavaScript sin frameworks, con tema día y noche |
| Autenticación y base de datos | Supabase: Auth con PKCE, Postgres con RLS y Storage |
| Despliegue | Render ([`render.yaml`](render.yaml)) |

### Ejecutar en local

Requiere **Python 3.11 o superior** (probado con 3.13).

```bash
git clone https://github.com/javiergilmr/digital-lab-app.git
cd digital-lab-app

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

pip install -r data-cleaner-app/requirements.txt
```

Crea un archivo `.env` en la raíz del repositorio con las claves de tu proyecto de Supabase:

```env
SUPABASE_URL=https://TU-PROYECTO.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_xxxxxxxxxxxxxxxx
```

Y arranca la app:

```bash
cd data-cleaner-app
python main.py
```

Abre **http://127.0.0.1:8000**.

La configuración completa de Supabase (URLs permitidas, login con Google y scripts SQL), las reglas de limpieza, las rutas de la API y las limitaciones conocidas están en el [README de la app](data-cleaner-app/README.md).

### Estructura

```
digital-lab-app/
├── render.yaml             # Despliegue en Render
└── data-cleaner-app/
    ├── main.py             # App FastAPI
    ├── routers/            # Rutas de la API, del login y de las páginas
    ├── services/           # Limpieza, análisis, PDF, Supabase y límite mensual
    ├── models/             # Datos que envía el navegador
    ├── supabase/           # Scripts SQL: tablas, RLS y funciones
    ├── templates/          # Páginas Jinja2
    └── static/             # CSS, JS y archivos CSV de ejemplo
```

---

## Licencia

© 2026 Javier Gil Moreno. Todos los derechos reservados.

El código se publica solo para consulta, como parte de un portafolio profesional. Para usarlo en otros proyectos hace falta permiso por escrito. Los términos completos están en [LICENSE](LICENSE).
