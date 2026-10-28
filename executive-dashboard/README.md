# Executive Dashboard

Dashboard ejecutivo minimalista en un solo `.html` (web + móvil, modo claro/oscuro), alimentado por SQL desde una base de datos ficticia.

## Inicio rápido (sin instalar nada)

Requiere solo Python 3.9+.

```bash
python server.py
```

Abre **http://localhost:8000**. La primera vez se crea `data/exec_dash.db` (SQLite) con 24 meses de datos ficticios, y el dashboard se conecta a la base de forma automática. En la barra lateral aparece *Conectado · SQLite*.

- **+ Simular venta** (en *Actividad reciente*) inserta una venta real en la base. Los KPIs y la actividad se actualizan al instante.
- El dashboard se refresca solo cada 60 segundos.
- `python server.py --reset` regenera la base desde cero.

## Estructura

```
executive-dashboard/
├── dashboard.html              # Dashboard (web + móvil)
├── server.py                   # Servidor + API (solo librería estándar)
├── data/exec_dash.db           # Base ficticia (se genera sola)
└── sql/
    ├── sqlite/                 # Motor local (por defecto)
    │   ├── 01_schema_seed.sql  #   esquema + datos ficticios
    │   └── 02_queries.sql      #   consultas del dashboard
    └── redshift/               # Mismo modelo para Amazon Redshift
        ├── 01_schema_seed.sql
        └── 02_queries.sql
```

## Cómo fluye la data

```
SQLite / Redshift  →  sql/<motor>/02_queries.sql  →  server.py (/api/dashboard)  →  dashboard.html
```

Cada bloque `-- name: <clave>` de `02_queries.sql` es un dataset del JSON:

| Dataset | Columnas |
|---|---|
| `ingresos_categoria` | mes, categoria, ingresos |
| `gastos_categoria` | mes, categoria, gastos |
| `ingresos_producto` | mes, producto, categoria, ingresos |
| `actividad` | ts, tipo, titulo, detalle |

El navegador calcula los KPIs (ingresos, gastos, utilidad, margen y sus variaciones). `kpis_mensuales` (y `GET /api/kpis`) calcula lo mismo en SQL para validar.

## API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/dashboard` | Todos los datasets + `meta` (motor) |
| GET | `/api/kpis` | KPIs mensuales calculados en SQL |
| POST | `/api/simular-venta` | Inserta una venta aleatoria |

## Usar Amazon Redshift

1. Ejecutar `sql/redshift/01_schema_seed.sql` (crea el esquema `exec_dash`).
2. `pip install redshift_connector`
3. Definir `REDSHIFT_HOST`, `REDSHIFT_USER`, `REDSHIFT_PASSWORD` (opcional `REDSHIFT_DB`, `REDSHIFT_PORT`).
4. `python server.py --backend redshift`

## Modo demo

Si abres `dashboard.html` con doble clic (sin servidor), usa datos generados en el navegador e indica *Datos demo*. `?demo` fuerza ese modo y `?api=<url>` apunta a otra API.
