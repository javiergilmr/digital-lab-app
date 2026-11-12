# Data Cleaner & Sales Report

Aplicación web que toma un archivo de ventas (CSV o Excel), **limpia los datos automáticamente**, genera un **informe de ventas** con utilidad, márgenes y desgloses, y permite descargar los datos limpios en **CSV** y el informe en **PDF**. El acceso está protegido con **Supabase Auth** (correo y contraseña o Google).

Construida con **FastAPI**, **pandas**, **Jinja2** y **reportlab**.

---

## Contenido

1. [Qué hace](#qué-hace)
2. [Flujo de uso](#flujo-de-uso)
3. [Instalación](#instalación)
4. [Configuración de Supabase](#configuración-de-supabase)
5. [Ejecutar la app](#ejecutar-la-app)
6. [Columnas que reconoce](#columnas-que-reconoce)
7. [Limpieza de datos](#limpieza-de-datos)
8. [Análisis e informe](#análisis-e-informe)
9. [Descargas](#descargas)
10. [Mi panel](#mi-panel)
11. [Estructura del proyecto](#estructura-del-proyecto)
12. [Rutas y API](#rutas-y-api)
13. [Seguridad](#seguridad)
14. [Limitaciones conocidas](#limitaciones-conocidas)

---

## Qué hace

- **Login obligatorio** con Supabase: correo y contraseña, o Google. Registro abierto, recuperación de contraseña y botón de “ojo” para ver la contraseña.
- **Carga de archivos** `.csv` o `.xlsx` arrastrándolos a la página o con el botón *Cargar archivo*.
- **Guía del archivo** en la página de carga: una mini hoja de ejemplo con las columnas obligatorias y opcionales, y un [CSV de ejemplo](static/ejemplo_ventas.csv) para descargar y probar.
- **Detección automática de columnas**: reconoce nombres en español e inglés (`fecha`, `transaction_date`, `precio`, `unit_price`…) y propone el mapeo.
- **Mapeo editable**: 4 columnas obligatorias y 7 opcionales que enriquecen el análisis.
- **Limpieza que corrige antes de eliminar**: deduce el valor correcto cuando los datos lo permiten y reporta cada cambio.
- **Informe de ventas**: total vendido, utilidad, margen, rankings, ventas por categoría, tienda y ciudad, tendencia mensual e insights automáticos.
- **Exportación** de los datos limpios a CSV y del informe a PDF, con el nombre de la empresa y la fecha.
- **Mi panel**: cada usuario ve sus archivos cargados, filas corregidas, último inicio de sesión y plan, un historial de sus últimos 10 informes con el PDF listo para volver a descargar, y la sección *Cuenta*: método de acceso, cambio de contraseña y eliminación de la cuenta.

## Flujo de uso

```
Login  →  Subir archivo  →  Mapear columnas  →  Procesar  →  Informe + descargas
 /login        /             /map/{id}         /clean/{id}
```

1. **Iniciar sesión** (o crear cuenta).
2. **Subir el archivo**. La app valida que parezca un archivo de ventas: si no encuentra fecha, producto, cantidad y precio, explica qué falta.
3. **Mapear columnas**. Cada campo viene preseleccionado; puedes cambiarlo o marcar las opcionales como *No usar*. Aquí también se escribe el **nombre del informe** (opcional, máximo 18 caracteres), por ejemplo `Fridays Company`.
4. **Procesar archivo**. Una barra de carga (mínimo 5 segundos) acompaña la limpieza y el análisis. Al terminar, el botón desaparece y un aviso flotante confirma el resultado.
5. **Revisar el informe** y descargar el CSV o el PDF.

## Instalación

Requisitos: **Python 3.11 o superior** (probado con 3.13).

Desde la raíz del repositorio (`digita-lab-app/`):

```bash
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install fastapi uvicorn pandas numpy openpyxl jinja2 python-multipart python-dotenv reportlab pydantic
```

| Paquete | Para qué se usa |
|---|---|
| `fastapi`, `uvicorn` | Servidor web y API |
| `jinja2` | Plantillas HTML |
| `python-multipart` | Recibir archivos y formularios |
| `pandas`, `numpy` | Limpieza y análisis |
| `openpyxl` | Leer archivos `.xlsx` |
| `reportlab` | Generar el PDF |
| `python-dotenv` | Leer el archivo `.env` |
| `pydantic` | Validar los datos que envía el navegador |

Versiones con las que se probó: fastapi 0.162.0, uvicorn 0.54.0, pandas 3.1.0, numpy 2.5.4, openpyxl 3.1.5, reportlab 5.1.0, Jinja2 3.1.6, python-dotenv 1.2.4, python-multipart 0.0.33, pydantic 2.14.2.

## Configuración de Supabase

### 1. Archivo `.env`

Crea un archivo `.env` en la **raíz del repositorio** (`digita-lab-app/.env`, no dentro de `data-cleaner-app/`):

```env
SUPABASE_URL=https://TU-PROYECTO.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_xxxxxxxxxxxxxxxx
```

Ambos valores están en el panel de Supabase, en **Project Settings → API Keys**. Si falta alguno, la app no arranca y muestra el error `Faltan SUPABASE_URL o SUPABASE_PUBLISHABLE_KEY en el archivo .env`.

> ⚠️ Usa solo la clave **publishable**. Nunca pongas la clave `sb_secret_…` / `service_role` en este proyecto: da acceso total a la base de datos. El `.env` ya está en `.gitignore`.

### 2. URLs permitidas

En **Authentication → URL Configuration**:

- **Site URL**: `http://127.0.0.1:8000`
- **Redirect URLs**: agrega `http://127.0.0.1:8000/**`

Son necesarias para el login con Google, la confirmación de correo y la recuperación de contraseña. Si publicas la app en otro dominio, agrega también ese dominio.

### 3. Login con Google (opcional)

En **Authentication → Sign In / Providers → Google**, activa el proveedor y pega el *Client ID* y el *Client Secret* de Google Cloud. El botón *Continuar con Google* aparece solo si el proveedor está activado.

### 4. Tablas y bucket del panel

En **SQL Editor → New query**, ejecuta estos tres scripts en orden. Cada uno se pega y se corre con **Run** una sola vez, y todos se pueden volver a ejecutar sin problema.

| Script | Qué crea |
|---|---|
| [`supabase/user_stats.sql`](supabase/user_stats.sql) | La tabla `user_stats`, con los contadores por usuario, y la función `record_activity`, que es la única forma de sumar a los contadores y no permite cambiar el plan |
| [`supabase/reports.sql`](supabase/reports.sql) | La tabla `reports`, con el historial de informes, y el bucket privado `reports` de Storage, donde van los PDFs: una carpeta por usuario, solo PDFs y hasta 5 MB cada uno |
| [`supabase/account.sql`](supabase/account.sql) | La función `delete_my_account`, que borra al usuario que la llama, y el permiso para que cada usuario borre sus propios PDFs |

Los scripts activan reglas de seguridad (RLS) para que cada usuario solo vea sus propios datos y archivos.

Si todavía no ejecutaste los scripts, la app funciona igual: el panel muestra un aviso, y la consola explica qué falta (`No se pudieron leer los stats del usuario`, `No se pudo guardar el PDF del informe`…).

### 5. Ver los usuarios registrados

En el panel de Supabase, en **Authentication → Users**. Las contraseñas las guarda Supabase cifradas; la app nunca las almacena.

## Ejecutar la app

```bash
cd data-cleaner-app
python main.py
```

Abre **http://127.0.0.1:8000** en el navegador. El servidor se recarga solo al guardar cambios en el código.

> Usa `127.0.0.1` y no `localhost`: las cookies de sesión y las URLs de Supabase están configuradas para esa dirección.

## Columnas que reconoce

La detección compara los nombres de las columnas sin importar mayúsculas, tildes, espacios ni guiones bajos. Una coincidencia exacta gana sobre una parcial, cada columna se asigna a un solo campo, y una columna de identificador (por ejemplo `product_id`) nunca se toma como nombre de producto.

### Obligatorias

| Campo | Etiqueta | Nombres que reconoce |
|---|---|---|
| `date` | Fecha | date, fecha, day, createdat, fecha_venta, transaction_date |
| `product` | Producto | product, producto, item, sku, descripcion, product_name, nombre_producto |
| `quantity` | Cantidad | quantity, qty, cantidad, units |
| `price` | Precio unitario | price, precio, unit_price, precio_unitario, amount, monto |

### Opcionales

Si vienen en el archivo, activan correcciones y secciones extra del informe. Si no vienen, todo funciona igual con las cuatro obligatorias.

| Campo | Etiqueta | Nombres que reconoce | Qué habilita |
|---|---|---|---|
| `category` | Categoría | category, categoria, rubro, linea, familia | Ventas por categoría |
| `store_id` | Tienda | store_id, id_tienda, tienda_id, sucursal_id, codigo_tienda, tienda, sucursal, store | Ventas por tienda |
| `store_city` | Ciudad | store_city, city, ciudad, ciudad_tienda, municipio | Ventas por ciudad |
| `net_sales` | Venta neta | net_sales, venta_neta, ventas_netas, total_neto, net_amount | Ingreso después de descuentos |
| `unit_cost` | Costo unitario | unit_cost, costo_unitario, cost, costo | Utilidad y margen |
| `total_cost` | Costo total | total_cost, costo_total | Utilidad y margen |
| `profit` | Utilidad | profit, utilidad, ganancia | Utilidad y margen |

Las columnas que no se mapean (por ejemplo `customer_id` o `payment_method`) **se conservan** en el CSV exportado.

### Validación al subir

- El archivo debe tener al menos 4 columnas y la app debe reconocer al menos 3 de las 4 obligatorias.
- Las columnas de fecha, cantidad y precio se aceptan si **al menos el 80 %** de sus valores son válidos. Un valor malo aislado (por ejemplo la fecha `2026-13-05`) no rechaza el archivo: lo resuelve la limpieza.
- Al mapear, si falta un campo obligatorio, la app indica cuál (`Faltan columnas obligatorias: Precio unitario.`).

## Limpieza de datos

La limpieza se ejecuta en este orden. Cada paso solo actúa si las columnas necesarias existen.

| # | Paso | Qué hace |
|---|---|---|
| 1 | Filas vacías | Elimina filas completamente vacías. |
| 2 | Espacios | Quita espacios de sobra (`"  arroz 5 LB "` → `"arroz 5 LB"`). |
| 3 | Escritura | Unifica variantes que solo difieren en mayúsculas, tildes o espacios, usando la forma más frecuente (`"Tarjeta debito"` → `"Tarjeta débito"`). Ignora columnas casi únicas, como los ids de transacción. |
| 4 | Fechas | Interpreta varios formatos y elimina las fechas imposibles. |
| 5 | Números | Convierte `19,99`, `1.500,75` o `$1,500.75`. En columnas opcionales, un valor no numérico se deja en blanco en vez de eliminar la fila. |
| 6 | Coherencia | Corrige la categoría según el producto y la ciudad según la tienda, cuando hay una mayoría clara (al menos 2 filas y más de la mitad). |
| 7 | Precio | Un precio negativo o vacío toma el precio habitual (mediana) del producto. Si no se puede deducir, la fila se elimina. |
| 8 | Cantidad | Una cantidad 0, vacía o negativa con venta positiva se deduce de costo total ÷ costo unitario, solo si da un número entero. Si no, la fila se elimina. |
| 9 | Totales | Recalcula el costo total (cantidad × costo unitario) y la utilidad (venta neta − costo total) cuando no cuadran por más de 2 centavos. Estima la venta neta vacía como cantidad × precio. |
| 10 | Obligatorios | Elimina filas sin fecha, producto, cantidad o precio. Una fila sin datos opcionales, como el cliente, **se conserva**. |
| 11 | Duplicados | Elimina filas duplicadas exactas. |

El resultado incluye un **reporte de limpieza**:

- Filas recibidas, corregidas, eliminadas y analizadas. Una fila con varias correcciones cuenta una sola vez.
- El detalle de cada acción, separado en *Corregido* y *Eliminado* (`Ciudad corregida según la tienda: 1 fila`).

Procesar el archivo otra vez, por ejemplo al recargar la página, siempre parte de los datos originales mapeados, así que el reporte no cambia.

## Análisis e informe

La página del informe (`/clean/{id}`) muestra, en este orden:

1. **Acerca de este informe**: un párrafo generado con el periodo, el número de transacciones, productos, categorías y tiendas, el total vendido, la utilidad, el margen, el producto top y el mejor mes. Debajo, una nota de cómo se calcularon las cifras.
2. **Total vendido** y resumen: transacciones, ticket promedio, producto top y mejor mes, más utilidad y margen si hay datos de costo.
3. **Top 5 productos por ingresos**.
4. **Top 5 productos por utilidad** (si hay datos de costo).
5. **Ventas por categoría**, **por tienda** y **por ciudad**, con participación y, si hay datos de costo, utilidad y margen. La tabla por ciudad solo aparece si alguna ciudad tiene más de una tienda; si no, repetiría la de tiendas.
6. **Ventas mensuales**: gráfico con Chart.js.
7. **Insights** automáticos, por ejemplo concentración de ingresos en 2 productos, crecimiento entre el primer y el último mes, la categoría que más utilidad deja, la de menor margen y la tienda que más vende.
8. **Limpieza de datos**: el reporte descrito arriba.

**Cómo se calculan las cifras:**

- **Ventas**: la venta neta si existe la columna; si no, cantidad × precio unitario.
- **Utilidad**: la columna de utilidad, o venta − costo total, o venta − cantidad × costo unitario.
- **Margen**: utilidad ÷ ventas.
- Todos los montos se muestran con 2 decimales y separador de miles (`$19,824.78`).

## Descargas

| Archivo | Con nombre de informe “Fridays Company” | Sin nombre |
|---|---|---|
| Datos limpios (CSV) | `fridays_company_data_2026-11-08.csv` | `datos_limpios_2026-11-08.csv` |
| Informe (PDF) | `fridays_company_report_2026-11-08.pdf` | `reporte_ventas_2026-11-08.pdf` |

- La fecha es la del día de la descarga.
- El nombre del archivo se forma con el nombre del informe en minúsculas, sin tildes y con `_` en lugar de espacios.
- En el PDF, el título es el nombre en mayúsculas seguido de *Sales Report* (`FRIDAYS COMPANY Sales Report`).
- El PDF incluye el resumen, los rankings, los desgloses, el gráfico mensual y los insights.

## Mi panel

La página **`/panel`** se abre desde el enlace *Mi panel* de la barra superior y muestra:

| Tarjeta | Qué muestra | De dónde sale |
|---|---|---|
| Archivos cargados | Archivos aceptados al subirlos | Suma 1 en cada carga exitosa |
| Filas corregidas | Filas que la limpieza arregló, más las eliminadas y las procesadas | Suma una vez por archivo procesado |
| Último inicio de sesión | Fecha y hora en la zona horaria de quien mira, más “Miembro desde” | Supabase Auth, que lo actualiza en cada inicio de sesión |
| Plan | *Gratuito* | Columna `plan` de `user_stats` (por defecto `free`) |

Arriba de las tarjetas, una frase resume el valor de la limpieza, por ejemplo: *“La app revisó 3,000 filas por ti y corrigió 18 sin que tuvieras que tocarlas. El 0.70 % de tus datos tenía algún error.”* El porcentaje cuenta las filas corregidas más las eliminadas, sobre el total procesado.

### Historial de informes

Debajo de las tarjetas aparecen los **últimos 10 informes** procesados. Cada uno muestra:

- El nombre del informe (o el del archivo, si no tiene nombre).
- La fecha y hora, el archivo original, las filas analizadas y las corregidas.
- El total vendido y el margen.
- Un botón **PDF** para volver a descargarlo, con el mismo nombre que la descarga original (`fridays_company_report_2026-11-11.pdf`).

Cómo funciona:

- **Cuándo se guarda:** la primera vez que se procesa un archivo, la app genera el PDF, lo sube a Storage (`reports/<user_id>/<id>.pdf`) y registra el resumen en la tabla `reports`. Procesarlo de nuevo no duplica la entrada.
- **Sin esperas:** se guarda en segundo plano, así que el informe aparece en pantalla igual de rápido.
- **Si falla la subida:** el informe aparece en el historial como *Sin PDF*.
- **Descarga:** el PDF se descarga a través de la app (`/panel/reports/{id}/pdf`), con el permiso del propio usuario. Nadie puede bajar el PDF de otro, aunque conozca el id.

- **Sin duplicados:** procesar el mismo archivo otra vez, por ejemplo al recargar el informe, no vuelve a sumar.
- **Sin esperas:** los contadores se guardan en Supabase después de responder, así que no hacen esperar al usuario.
- **Sin bloqueos:** si Supabase falla, la carga y la limpieza siguen funcionando.

Para cambiar el plan de un usuario en el futuro, edita la columna `plan` en **Table Editor → user_stats**. La etiqueta que se muestra se define en `PLANS`, en [`services/user_stats.py`](services/user_stats.py).

### Cuenta

Al final del panel, la sección **Cuenta** muestra:

- **Correo y método de acceso:** *Correo y contraseña*, *Google* o ambos, según cómo se registró el usuario.
- **Cambiar contraseña:** pide la contraseña actual, la nueva y su confirmación, con el “ojo” para verlas.
  - La contraseña actual se verifica iniciando sesión con ella, así que alguien con la sesión abierta no puede cambiarla.
  - La sesión actual sigue abierta después del cambio.
  - Si el usuario entra solo con Google, en lugar del formulario aparece una nota: su cuenta no tiene contraseña propia.
- **Eliminar cuenta:** un bloque desplegable que explica qué se borra y pide escribir el correo para confirmar.
  - La app borra primero los PDFs del usuario en Storage y luego la cuenta con `delete_my_account`. Sus filas de `user_stats` y `reports` se borran solas, en cascada.
  - Al terminar, cierra la sesión y muestra en el login “Tu cuenta y todos tus datos fueron eliminados.”
  - Si no puede borrar los PDFs, se detiene sin borrar la cuenta, para no dejar archivos huérfanos.

## Estructura del proyecto

```
data-cleaner-app/
├── main.py                  # App FastAPI: middleware de login, carga, mapeo, limpieza, análisis y exportaciones
├── models/
│   └── payloads.py          # Datos del mapeo que envía el navegador (incluye el nombre del informe)
├── routers/
│   ├── api.py               # /api/health
│   ├── auth.py              # Login, registro, Google, recuperación de contraseña, logout y cookies
│   └── pages.py             # Página de inicio
├── services/
│   ├── schema.py            # Campos obligatorios y opcionales, nombres alternativos y etiquetas
│   ├── auto_mapping.py      # Detección de columnas por puntaje
│   ├── column_validator.py  # Validación del archivo al subirlo
│   ├── mapping.py           # Aplica el mapeo elegido y valida los obligatorios
│   ├── cleaner.py           # Limpieza de datos y reporte de cambios
│   ├── analyzer.py          # Métricas, desgloses, descripción del informe e insights
│   ├── pdf_report.py        # Construcción del PDF y nombres de archivo
│   ├── sessions.py          # Sesiones en memoria, una por archivo y por usuario
│   ├── supabase_auth.py     # Cliente de Supabase: Auth, API de datos y Storage (solo librería estándar)
│   ├── user_stats.py        # Stats del panel: guardar actividad y leerla
│   ├── report_history.py    # Historial de informes: guardar resumen y PDF, listar y descargar
│   └── account.py           # Cuenta: método de acceso, cambio de contraseña y eliminación
├── supabase/
│   ├── user_stats.sql       # Tabla, seguridad y función de los stats (se pega en el SQL Editor)
│   ├── reports.sql          # Tabla del historial y bucket de PDFs (se pega en el SQL Editor)
│   └── account.sql          # Función para eliminar la cuenta y permiso para borrar PDFs
├── templates/
│   ├── _user_bar.html       # Barra con “Mi panel”, el correo del usuario y “Cerrar sesión”
│   ├── auth.html            # Login, registro y contraseñas
│   ├── index.html           # Carga de archivos (arrastrar y soltar)
│   ├── map.html             # Mapeo de columnas y nombre del informe
│   ├── panel.html           # Mi panel: stats del usuario
│   └── clean.html           # Procesamiento, informe y descargas
└── static/
    ├── css/styles.css       # Estilos compartidos
    ├── css/main.js
    ├── js/upload.js         # Carga de archivos
    ├── js/password_toggle.js # “Ojo” para mostrar u ocultar contraseñas (login, registro y panel)
    └── ejemplo_ventas.csv   # Archivo de ejemplo que se descarga desde la guía de carga
```

## Rutas y API

Todas las rutas requieren sesión iniciada, excepto las marcadas como públicas.

### Páginas

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Carga de archivos |
| GET | `/map/{session_id}` | Mapeo de columnas |
| GET | `/clean/{session_id}` | Procesamiento e informe |
| GET | `/panel` | Mi panel |
| GET | `/panel/reports/{id}/pdf` | Vuelve a descargar el PDF de un informe del historial |
| POST | `/panel/password` | Cambia la contraseña (pide la actual) |
| POST | `/panel/delete-account` | Elimina la cuenta y todos sus datos (pide escribir el correo) |
| GET/POST | `/login` | Inicio de sesión (pública) |
| GET/POST | `/signup` | Registro (pública) |
| GET/POST | `/forgot-password` | Pedir enlace para cambiar la contraseña (pública) |
| GET/POST | `/reset-password` | Crear una contraseña nueva |
| GET | `/auth/google` | Inicio de sesión con Google (pública) |
| GET | `/auth/callback` | Regreso desde Supabase (pública) |
| POST | `/logout` | Cerrar sesión |

### API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/health` | Estado del servidor (pública) |
| POST | `/api/upload` | Sube el archivo y crea la sesión |
| POST | `/api/map-columns/{session_id}` | Guarda el mapeo y el nombre del informe |
| POST | `/api/clean-data/{session_id}` | Limpia los datos y devuelve el reporte |
| POST | `/api/analyze/{session_id}` | Devuelve el análisis completo |
| GET | `/export/{session_id}` | Descarga el CSV limpio |
| GET | `/export-pdf/{session_id}` | Descarga el PDF (requiere haber procesado) |

## Seguridad

- **Login con PKCE** para Google, confirmación de correo y recuperación de contraseña.
- **Cookies `httponly`** (`sb_access`, `sb_refresh`), con `samesite=lax` y `secure` cuando la app corre en HTTPS. El token de acceso se renueva solo con el de refresco cuando vence.
- **Stats protegidos con RLS**: la app lee y escribe los stats con el token del propio usuario, nunca con una clave de administrador.
- **Sesiones por usuario**: cada archivo subido pertenece a quien lo subió. Otro usuario no puede verlo aunque conozca el id.
- **Redirecciones seguras**: el parámetro `?next=` solo acepta rutas internas.
- **Sin claves secretas**: la app solo usa la clave publishable de Supabase, y el `.env` está fuera de git.

## Limitaciones conocidas

- **Sesiones en memoria**: los archivos subidos se pierden al reiniciar el servidor, y la app está pensada para un solo proceso. Los informes ya procesados sí quedan guardados en el historial del panel, con su PDF.
- **Espacio en Storage**: cada PDF pesa alrededor de 10 KB. El plan gratuito de Supabase incluye 1 GB, así que alcanza para decenas de miles de informes.
- **Precio deducido aproximado**: un precio corregido toma la mediana del producto, que puede no ser el valor real. Si existe la venta neta, los totales no se ven afectados porque el ingreso sale de ella.
- **Sinónimos no se unifican**: solo se unifican variantes de escritura. Por ejemplo, `Online` y `E-commerce` quedan como valores distintos.
- **El PDF no incluye** la sección *Acerca de este informe* ni el reporte de limpieza: se muestran solo en la página.

---

© JAGM Data Cleaner & Sales Report 2026
