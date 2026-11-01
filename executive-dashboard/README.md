# Executive Dashboard

Dashboard ejecutivo minimalista en un solo `.html` (web + móvil, modo claro/oscuro), alimentado por SQL desde una base de datos ficticia.

## Inicio rápido (sin instalar nada)

Requiere solo Python 3.9+.

```bash
python server.py --dataset demo
```

Abre **http://localhost:8000**. La primera vez se crea `data/exec_dash.db` (SQLite) con 24 meses de datos ficticios, y el dashboard se conecta a la base de forma automática. En la barra lateral aparece *Conectado · SQLite*.

- **+ Simular venta** (en *Actividad reciente*) inserta una venta real en la base. Los KPIs y la actividad se actualizan al instante.
- El dashboard se refresca solo cada 60 segundos.
- `python server.py --dataset demo --reset` regenera la base desde cero.
- `python server.py` abre Olist por defecto (ver abajo). Mientras no exista `data/olist.db`, el dashboard muestra una muestra con forma de Olist marcada como *Datos demo*. La base ficticia de Acme solo se usa con `--dataset demo`.

## Estructura

```
executive-dashboard/
├── dashboard.html              # Dashboard (web + móvil)
├── server.py                   # Servidor + API (solo librería estándar)
├── load_olist.py               # Carga el dataset público de Olist
├── data/                       # Bases SQLite y CSV crudos (no se suben a GitHub)
└── sql/
    ├── sqlite/                 # Motor local (por defecto)
    │   ├── 00_schema.sql       #   modelo de datos (común a ambas fuentes)
    │   ├── 01_seed_demo.sql    #   datos ficticios
    │   └── 02_queries.sql      #   consultas del dashboard
    └── redshift/               # Mismo modelo para Amazon Redshift
        ├── 01_schema_seed.sql
        └── 02_queries.sql
```

## Datos reales: Olist (e-commerce de Brasil)

[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce): ~100k pedidos reales de 2016–2018. Licencia CC BY-NC-SA 4.0, uso no comercial y con atribución.

1. Descargar el dataset de Kaggle y descomprimir los CSV en `data/raw/olist/`.
2. `python load_olist.py` crea `data/olist.db` con el mismo modelo de datos.
3. `python server.py` (Olist es el dataset por defecto) y abrir http://localhost:8000.

Qué se usa del dataset:
- **Ingresos** = precio + flete de cada línea de pedido (real). Se excluyen pedidos cancelados o no disponibles.
- **Periodo**: ene-2017 a ago-2018. Los meses de los extremos tienen muy pocos pedidos.
- **Categorías**: las ~70 de Olist se agrupan en 5 macro-categorías. Cada categoría original es un "producto".
- **Actividad**: últimos pedidos y últimas reseñas de 1–2 estrellas (reales).
- **Gastos**: Olist no publica costos, así que se **modelan** con supuestos documentados en `SUPUESTOS` (`load_olist.py`): mercancía 60%, flete real, marketing 7%, comisiones 2.5% y fijo de R$25,000 al mes.

En el dashboard, con Olist:
- KPIs extra con datos reales: **clientes únicos** y **ticket por cliente** (dataset `resumen_mensual`).
- Gastos, utilidad y margen llevan la etiqueta *Modelado*, y la dona muestra el supuesto de cada gasto (dataset `supuestos_gastos`).
- El Top 5 muestra categorías originales de Olist con su macro-categoría.
- El **segmentador de categorías** (junto al mes) funciona como en Power BI: casillas por macro-categoría y por producto (ej. *Hogar y muebles › Muebles y decoración*), selección múltiple, grupos que se expanden y un buscador por texto (sin distinguir acentos). Sin nada marcado no se filtra. Aplica a los 6 KPIs y a la gráfica, resalta las categorías elegidas y filtra el Top 5. Con más de una categoría o producto, *Clientes únicos* y *Ticket* se marcan como aproximados: un cliente que compró en varios se cuenta más de una vez. `load_olist.py` atribuye los gastos a cada producto: la parte variable con su precio y flete reales, y el costo fijo según su participación en los ingresos (datasets `resumen_categoria`, `gastos_por_categoria_ingreso`, `resumen_producto` y `gastos_por_producto`). Con la base ficticia, los gastos se prorratean según los ingresos.

Este dataset es de solo lectura: el botón *Simular venta* se oculta.

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

Si abres `dashboard.html` con doble clic (sin servidor), usa datos de muestra generados en el navegador con la misma forma que Olist e indica *Datos demo*. `?demo` fuerza ese modo y `?api=<url>` apunta a otra API.
