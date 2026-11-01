-- =====================================================================
-- Executive Dashboard · Esquema (SQLite)
-- Lo usan las dos fuentes: la base ficticia (01_seed_demo.sql) y la
-- carga del dataset público de Olist (load_olist.py).
-- Mismo modelo que sql/redshift/01_schema_seed.sql.
-- =====================================================================

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS fact_ingresos;
DROP TABLE IF EXISTS fact_gastos;
DROP TABLE IF EXISTS log_actividad;
DROP TABLE IF EXISTS dim_producto;
DROP TABLE IF EXISTS dim_categoria_ingreso;
DROP TABLE IF EXISTS dim_categoria_gasto;

CREATE TABLE dim_categoria_ingreso (
    categoria_id INTEGER PRIMARY KEY,
    nombre       TEXT NOT NULL
);

CREATE TABLE dim_categoria_gasto (
    categoria_id INTEGER PRIMARY KEY,
    nombre       TEXT NOT NULL
);

CREATE TABLE dim_producto (
    producto_id  INTEGER PRIMARY KEY,
    nombre       TEXT NOT NULL,
    categoria_id INTEGER NOT NULL REFERENCES dim_categoria_ingreso (categoria_id)
);

CREATE TABLE fact_ingresos (
    ingreso_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha       TEXT    NOT NULL,              -- 'YYYY-MM-DD'
    cliente     TEXT,
    producto_id INTEGER NOT NULL REFERENCES dim_producto (producto_id),
    monto       REAL    NOT NULL
);
CREATE INDEX ix_ingresos_fecha ON fact_ingresos (fecha);

CREATE TABLE fact_gastos (
    gasto_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha        TEXT    NOT NULL,
    categoria_id INTEGER NOT NULL REFERENCES dim_categoria_gasto (categoria_id),
    categoria_ingreso_id INTEGER REFERENCES dim_categoria_ingreso (categoria_id),  -- opcional: gasto atribuido a una categoría de ingreso (Olist)
    producto_id  INTEGER REFERENCES dim_producto (producto_id),                    -- opcional: gasto atribuido a un producto (Olist)
    descripcion  TEXT,
    monto        REAL    NOT NULL
);
CREATE INDEX ix_gastos_fecha ON fact_gastos (fecha);

CREATE TABLE log_actividad (
    evento_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,                   -- ISO 8601 UTC
    tipo      TEXT NOT NULL,                   -- venta | pago | cliente | reporte | resena
    titulo    TEXT NOT NULL,
    detalle   TEXT
);
