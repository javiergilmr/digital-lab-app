-- =====================================================================
-- Executive Dashboard · Consultas (SQLite)
-- Equivalentes 1:1 a sql/redshift/02_queries.sql (mismas columnas).
-- Cada bloque "-- name: <clave>" es un dataset del JSON del dashboard.
-- La ventana de 24 meses se ancla a la fecha más reciente de los datos
-- (no a hoy), para que funcione igual con datos históricos como Olist.
-- =====================================================================

-- name: ingresos_categoria
SELECT strftime('%Y-%m', f.fecha) AS mes,
       c.nombre                   AS categoria,
       round(sum(f.monto), 0)     AS ingresos
FROM fact_ingresos f
JOIN dim_producto p          ON p.producto_id  = f.producto_id
JOIN dim_categoria_ingreso c ON c.categoria_id = p.categoria_id
WHERE f.fecha >= (SELECT date(max(fecha), 'start of month', '-23 months') FROM fact_ingresos)
GROUP BY 1, 2
ORDER BY 1, 2;

-- name: gastos_categoria
SELECT strftime('%Y-%m', g.fecha) AS mes,
       c.nombre                   AS categoria,
       round(sum(g.monto), 0)     AS gastos
FROM fact_gastos g
JOIN dim_categoria_gasto c ON c.categoria_id = g.categoria_id
WHERE g.fecha >= (SELECT date(max(fecha), 'start of month', '-23 months') FROM fact_ingresos)
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
WHERE f.fecha >= (SELECT date(max(fecha), 'start of month', '-23 months') FROM fact_ingresos)
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


-- name: resumen_mensual
-- Volumen del mes: líneas vendidas y clientes únicos (en Olist, customer_unique_id)
SELECT strftime('%Y-%m', fecha)  AS mes,
       count(*)                  AS articulos,
       count(DISTINCT cliente)   AS clientes,
       round(sum(monto), 0)      AS ingresos
FROM fact_ingresos
WHERE fecha >= (SELECT date(max(fecha), 'start of month', '-23 months') FROM fact_ingresos)
GROUP BY 1
ORDER BY 1;

-- name: supuestos_gastos
-- Cómo se calculó cada categoría de gasto (en Olist son supuestos de load_olist.py)
SELECT c.nombre AS categoria, max(g.descripcion) AS descripcion
FROM fact_gastos g
JOIN dim_categoria_gasto c ON c.categoria_id = g.categoria_id
GROUP BY c.categoria_id, c.nombre
ORDER BY c.categoria_id;

-- name: resumen_categoria
-- Igual que resumen_mensual, por categoría de ingreso (para el filtro del dashboard)
SELECT strftime('%Y-%m', f.fecha)  AS mes,
       c.nombre                    AS categoria,
       count(*)                    AS articulos,
       count(DISTINCT f.cliente)   AS clientes
FROM fact_ingresos f
JOIN dim_producto p          ON p.producto_id  = f.producto_id
JOIN dim_categoria_ingreso c ON c.categoria_id = p.categoria_id
WHERE f.fecha >= (SELECT date(max(fecha), 'start of month', '-23 months') FROM fact_ingresos)
GROUP BY 1, 2
ORDER BY 1, 2;

-- name: gastos_por_categoria_ingreso
-- Gastos atribuidos a cada categoría de ingreso. Vacío si la base no los atribuye
-- (base ficticia): el dashboard entonces los prorratea según los ingresos.
SELECT strftime('%Y-%m', g.fecha) AS mes,
       c.nombre                   AS categoria,
       round(sum(g.monto), 0)     AS gastos
FROM fact_gastos g
JOIN dim_categoria_ingreso c ON c.categoria_id = g.categoria_ingreso_id
WHERE g.fecha >= (SELECT date(max(fecha), 'start of month', '-23 months') FROM fact_ingresos)
GROUP BY 1, 2
ORDER BY 1, 2;

-- name: resumen_producto
-- Igual que resumen_categoria, por producto (en Olist, cada categoría original)
SELECT strftime('%Y-%m', f.fecha)  AS mes,
       p.nombre                    AS producto,
       count(*)                    AS articulos,
       count(DISTINCT f.cliente)   AS clientes
FROM fact_ingresos f
JOIN dim_producto p ON p.producto_id = f.producto_id
WHERE f.fecha >= (SELECT date(max(fecha), 'start of month', '-23 months') FROM fact_ingresos)
GROUP BY 1, 2
ORDER BY 1, 2;

-- name: gastos_por_producto
-- Gastos atribuidos a cada producto. Vacío si la base no los atribuye: el dashboard
-- entonces los prorratea según los ingresos.
SELECT strftime('%Y-%m', g.fecha) AS mes,
       p.nombre                   AS producto,
       round(sum(g.monto), 0)     AS gastos
FROM fact_gastos g
JOIN dim_producto p ON p.producto_id = g.producto_id
WHERE g.fecha >= (SELECT date(max(fecha), 'start of month', '-23 months') FROM fact_ingresos)
GROUP BY 1, 2
ORDER BY 1, 2;
