-- =====================================================================
-- Executive Dashboard · Consultas (SQLite)
-- Equivalentes 1:1 a sql/redshift/02_queries.sql (mismas columnas).
-- Cada bloque "-- name: <clave>" es un dataset del JSON del dashboard.
-- =====================================================================

-- name: ingresos_categoria
SELECT strftime('%Y-%m', f.fecha) AS mes,
       c.nombre                   AS categoria,
       round(sum(f.monto), 0)     AS ingresos
FROM fact_ingresos f
JOIN dim_producto p          ON p.producto_id  = f.producto_id
JOIN dim_categoria_ingreso c ON c.categoria_id = p.categoria_id
WHERE f.fecha >= date('now', 'localtime', 'start of month', '-23 months')
GROUP BY 1, 2
ORDER BY 1, 2;

-- name: gastos_categoria
SELECT strftime('%Y-%m', g.fecha) AS mes,
       c.nombre                   AS categoria,
       round(sum(g.monto), 0)     AS gastos
FROM fact_gastos g
JOIN dim_categoria_gasto c ON c.categoria_id = g.categoria_id
WHERE g.fecha >= date('now', 'localtime', 'start of month', '-23 months')
GROUP BY 1, 2
ORDER BY 1, 2;

-- name: ingresos_producto
SELECT strftime('%Y-%m', f.fecha) AS mes,
       p.nombre                   AS producto,
       c.nombre                   AS categoria,
       round(sum(f.monto), 0)     AS ingresos
FROM fact_ingresos f
JOIN dim_producto p          ON p.producto_id  = f.producto_id
JOIN dim_categoria_ingreso c ON c.categoria_id = p.categoria_id
WHERE f.fecha >= date('now', 'localtime', 'start of month', '-23 months')
GROUP BY 1, 2, 3
ORDER BY 1, 4 DESC;

-- name: actividad
SELECT ts, tipo, titulo, detalle
FROM log_actividad
ORDER BY ts DESC
LIMIT 8;

-- name: kpis_mensuales
WITH ing AS (
    SELECT strftime('%Y-%m', fecha) AS mes, sum(monto) AS ingresos FROM fact_ingresos GROUP BY 1
), gas AS (
    SELECT strftime('%Y-%m', fecha) AS mes, sum(monto) AS gastos FROM fact_gastos GROUP BY 1
), meses AS (
    SELECT mes FROM ing UNION SELECT mes FROM gas
), m AS (
    SELECT x.mes, coalesce(i.ingresos, 0) AS ingresos, coalesce(g.gastos, 0) AS gastos
    FROM meses x LEFT JOIN ing i ON i.mes = x.mes LEFT JOIN gas g ON g.mes = x.mes
)
SELECT mes,
       round(ingresos, 0)                                             AS ingresos,
       round(gastos, 0)                                               AS gastos,
       round(ingresos - gastos, 0)                                    AS utilidad,
       round(100.0 * (ingresos - gastos) / nullif(ingresos, 0), 1)    AS margen_pct,
       round(100.0 * (ingresos / nullif(lag(ingresos) OVER (ORDER BY mes), 0) - 1), 1) AS var_ingresos_pct,
       round(100.0 * (gastos   / nullif(lag(gastos)   OVER (ORDER BY mes), 0) - 1), 1) AS var_gastos_pct
FROM m
ORDER BY mes;
