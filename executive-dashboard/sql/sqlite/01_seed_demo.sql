-- =====================================================================
-- Executive Dashboard · Datos ficticios (SQLite)
-- Se ejecuta después de 00_schema.sql. server.py lo corre solo si
-- data/exec_dash.db no existe (o con --reset).
-- =====================================================================

INSERT INTO dim_categoria_ingreso VALUES
 (1,'Ventas'),(2,'Servicios'),(3,'Productos'),(4,'Otros');

INSERT INTO dim_categoria_gasto VALUES
 (1,'Personal'),(2,'Operaciones'),(3,'Marketing'),(4,'Tecnología'),(5,'Otros');

INSERT INTO dim_producto VALUES
 (1,'Desarrollo de Software',1),(2,'Implementaciones',1),
 (3,'Consultoría Premium',2),(4,'Soporte Técnico',2),
 (5,'Licencias',3),(6,'Hosting',3),
 (7,'Capacitación',4),(8,'Auditoría',4);

-- Pseudo-aleatorios deterministas a partir de n (hash multiplicativo): datos reproducibles.
-- No se usa random() porque SQLite lo re-evalúa en cada referencia a la CTE.

-- Ingresos: 2,920 transacciones (4 por día durante 730 días), con tendencia creciente
INSERT INTO fact_ingresos (fecha, cliente, producto_id, monto)
WITH RECURSIVE nums(n) AS (SELECT 0 UNION ALL SELECT n + 1 FROM nums WHERE n < 2919),
t AS (
    SELECT n,
           ((n * 2654435761) % 4294967296) / 4294967296.0 AS r1,
           ((n * 40503 + 12345) % 65536) / 65536.0        AS r2
    FROM nums
)
SELECT date('now', 'localtime', '-' || (n % 730) || ' days'),
       'Cliente ' || printf('%02d', (n * 7) % 60 + 1),
       CASE WHEN r1 < .30 THEN 1 WHEN r1 < .50 THEN 2 WHEN r1 < .64 THEN 3
            WHEN r1 < .73 THEN 4 WHEN r1 < .83 THEN 5 WHEN r1 < .88 THEN 6
            WHEN r1 < .95 THEN 7 ELSE 8 END,
       round((300 + r2 * 1200) * (0.75 + 0.5 * (1 - (n % 730) / 730.0)), 2)
FROM t;

-- Gastos: 1,460 registros (2 por día durante 730 días)
INSERT INTO fact_gastos (fecha, categoria_id, descripcion, monto)
WITH RECURSIVE nums(n) AS (SELECT 0 UNION ALL SELECT n + 1 FROM nums WHERE n < 1459),
t AS (
    SELECT n,
           ((n * 2246822519 + 7) % 4294967296) / 4294967296.0 AS r1,
           ((n * 69069 + 1013) % 65536) / 65536.0             AS r2
    FROM nums
)
SELECT date('now', 'localtime', '-' || (n % 730) || ' days'),
       CASE WHEN r1 < .42 THEN 1 WHEN r1 < .65 THEN 2 WHEN r1 < .80 THEN 3
            WHEN r1 < .90 THEN 4 ELSE 5 END,
       'Gasto #' || n,
       round((350 + r2 * 1500) * (0.8 + 0.4 * (1 - (n % 730) / 730.0)), 2)
FROM t;

-- Actividad reciente
INSERT INTO log_actividad (ts, tipo, titulo, detalle) VALUES
 (strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '-2 hours'),  'venta',   'Nueva venta registrada',   'Cliente: TechSolutions'),
 (strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '-4 hours'),  'pago',    'Pago recibido',            '$4,800 · Consultoría Premium'),
 (strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '-6 hours'),  'cliente', 'Nuevo cliente',            'Global Systems Inc.'),
 (strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '-8 hours'),  'reporte', 'Reporte mensual generado', 'Cierre del mes anterior'),
 (strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '-27 hours'), 'venta',   'Nueva venta registrada',   'Cliente: Nova Retail');
