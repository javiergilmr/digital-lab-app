-- =====================================================================
-- Executive Dashboard · Consultas que alimentan el dashboard (Redshift)
-- Cada bloque "-- name: <clave>" devuelve un dataset del JSON que
-- consume dashboard.html. api.py lee este archivo y las ejecuta.
-- =====================================================================

-- name: ingresos_categoria
SELECT TO_CHAR(DATE_TRUNC('month', f.fecha), 'YYYY-MM') AS mes,
       c.nombre                                         AS categoria,
       ROUND(SUM(f.monto), 0)                           AS ingresos
FROM exec_dash.fact_ingresos f
JOIN exec_dash.dim_producto p          ON p.producto_id  = f.producto_id
JOIN exec_dash.dim_categoria_ingreso c ON c.categoria_id = p.categoria_id
WHERE f.fecha >= DATEADD(month, -23, DATE_TRUNC('month', CURRENT_DATE))
GROUP BY 1, 2
ORDER BY 1, 2;

-- name: gastos_categoria
SELECT TO_CHAR(DATE_TRUNC('month', g.fecha), 'YYYY-MM') AS mes,
       c.nombre                                         AS categoria,
       ROUND(SUM(g.monto), 0)                           AS gastos
FROM exec_dash.fact_gastos g
JOIN exec_dash.dim_categoria_gasto c ON c.categoria_id = g.categoria_id
WHERE g.fecha >= DATEADD(month, -23, DATE_TRUNC('month', CURRENT_DATE))
GROUP BY 1, 2
ORDER BY 1, 2;

-- name: ingresos_producto
SELECT TO_CHAR(DATE_TRUNC('month', f.fecha), 'YYYY-MM') AS mes,
       p.nombre                                         AS producto,
       c.nombre                                         AS categoria,
       ROUND(SUM(f.monto), 0)                           AS ingresos
FROM exec_dash.fact_ingresos f
JOIN exec_dash.dim_producto p          ON p.producto_id  = f.producto_id
JOIN exec_dash.dim_categoria_ingreso c ON c.categoria_id = p.categoria_id
WHERE f.fecha >= DATEADD(month, -23, DATE_TRUNC('month', CURRENT_DATE))
GROUP BY 1, 2, 3
ORDER BY 1, 4 DESC;

-- name: actividad
SELECT ts, tipo, titulo, detalle
FROM exec_dash.log_actividad
ORDER BY ts DESC
LIMIT 8;

-- name: kpis_mensuales
-- (Validación: los mismos KPI que calcula el dashboard, hechos en SQL)
WITH ing AS (
    SELECT DATE_TRUNC('month', fecha) AS mes, SUM(monto) AS ingresos
    FROM exec_dash.fact_ingresos GROUP BY 1
), gas AS (
    SELECT DATE_TRUNC('month', fecha) AS mes, SUM(monto) AS gastos
    FROM exec_dash.fact_gastos GROUP BY 1
), m AS (
    SELECT COALESCE(i.mes, g.mes)      AS mes,
           COALESCE(i.ingresos, 0)     AS ingresos,
           COALESCE(g.gastos, 0)       AS gastos
    FROM ing i FULL OUTER JOIN gas g ON g.mes = i.mes
)
SELECT TO_CHAR(mes, 'YYYY-MM')                                               AS mes,
       ROUND(ingresos, 0)                                                    AS ingresos,
       ROUND(gastos, 0)                                                      AS gastos,
       ROUND(ingresos - gastos, 0)                                           AS utilidad,
       ROUND(100.0 * (ingresos - gastos) / NULLIF(ingresos, 0), 1)           AS margen_pct,
       ROUND(100.0 * (ingresos / NULLIF(LAG(ingresos) OVER (ORDER BY mes), 0) - 1), 1) AS var_ingresos_pct,
       ROUND(100.0 * (gastos   / NULLIF(LAG(gastos)   OVER (ORDER BY mes), 0) - 1), 1) AS var_gastos_pct
FROM m
ORDER BY mes;
