-- =====================================================================
-- Executive Dashboard · Esquema + datos ficticios (Amazon Redshift)
-- Ejecutar una sola vez. Genera ~24 meses de transacciones.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS exec_dash;

-- ---------- Dimensiones ----------
DROP TABLE IF EXISTS exec_dash.fact_ingresos;
DROP TABLE IF EXISTS exec_dash.fact_gastos;
DROP TABLE IF EXISTS exec_dash.log_actividad;
DROP TABLE IF EXISTS exec_dash.dim_producto;
DROP TABLE IF EXISTS exec_dash.dim_categoria_ingreso;
DROP TABLE IF EXISTS exec_dash.dim_categoria_gasto;

CREATE TABLE exec_dash.dim_categoria_ingreso (
    categoria_id SMALLINT     NOT NULL,
    nombre       VARCHAR(50)  NOT NULL,
    PRIMARY KEY (categoria_id)
) DISTSTYLE ALL;

CREATE TABLE exec_dash.dim_categoria_gasto (
    categoria_id SMALLINT     NOT NULL,
    nombre       VARCHAR(50)  NOT NULL,
    PRIMARY KEY (categoria_id)
) DISTSTYLE ALL;

CREATE TABLE exec_dash.dim_producto (
    producto_id  SMALLINT     NOT NULL,
    nombre       VARCHAR(100) NOT NULL,
    categoria_id SMALLINT     NOT NULL REFERENCES exec_dash.dim_categoria_ingreso (categoria_id),
    PRIMARY KEY (producto_id)
) DISTSTYLE ALL;

-- ---------- Hechos ----------
CREATE TABLE exec_dash.fact_ingresos (
    ingreso_id   BIGINT IDENTITY(1,1),
    fecha        DATE          NOT NULL,
    cliente      VARCHAR(100),
    producto_id  SMALLINT      NOT NULL,
    monto        DECIMAL(14,2) NOT NULL
) DISTSTYLE EVEN SORTKEY (fecha);

CREATE TABLE exec_dash.fact_gastos (
    gasto_id     BIGINT IDENTITY(1,1),
    fecha        DATE          NOT NULL,
    categoria_id SMALLINT      NOT NULL,
    descripcion  VARCHAR(200),
    monto        DECIMAL(14,2) NOT NULL
) DISTSTYLE EVEN SORTKEY (fecha);

CREATE TABLE exec_dash.log_actividad (
    evento_id    BIGINT IDENTITY(1,1),
    ts           TIMESTAMP     NOT NULL,
    tipo         VARCHAR(20)   NOT NULL,   -- venta | pago | cliente | reporte
    titulo       VARCHAR(100)  NOT NULL,
    detalle      VARCHAR(200)
) DISTSTYLE EVEN SORTKEY (ts);

-- ---------- Datos de dimensiones ----------
INSERT INTO exec_dash.dim_categoria_ingreso VALUES
 (1,'Ventas'),(2,'Servicios'),(3,'Productos'),(4,'Otros');

INSERT INTO exec_dash.dim_categoria_gasto VALUES
 (1,'Personal'),(2,'Operaciones'),(3,'Marketing'),(4,'Tecnología'),(5,'Otros');

INSERT INTO exec_dash.dim_producto VALUES
 (1,'Desarrollo de Software',1),(2,'Implementaciones',1),
 (3,'Consultoría Premium',2),(4,'Soporte Técnico',2),
 (5,'Licencias',3),(6,'Hosting',3),
 (7,'Capacitación',4),(8,'Auditoría',4);

-- ---------- Tabla de números (Redshift no permite generate_series en compute nodes) ----------
CREATE TEMP TABLE digits AS
SELECT 0 AS n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9;

CREATE TEMP TABLE nums AS
SELECT a.n + b.n*10 + c.n*100 + d.n*1000 AS n
FROM digits a CROSS JOIN digits b CROSS JOIN digits c CROSS JOIN digits d;   -- 0..9999

-- ---------- Ingresos ficticios (~3,000 transacciones en 730 días, con tendencia creciente) ----------
INSERT INTO exec_dash.fact_ingresos (fecha, cliente, producto_id, monto)
SELECT
    DATEADD(day, -(n % 730), CURRENT_DATE)::DATE                       AS fecha,
    'Cliente ' || LPAD(((n * 7) % 60 + 1)::VARCHAR, 2, '0')            AS cliente,
    CASE WHEN r1 < .30 THEN 1 WHEN r1 < .50 THEN 2 WHEN r1 < .64 THEN 3
         WHEN r1 < .73 THEN 4 WHEN r1 < .83 THEN 5 WHEN r1 < .88 THEN 6
         WHEN r1 < .95 THEN 7 ELSE 8 END                               AS producto_id,
    ROUND((300 + r2 * 1200) * (0.75 + 0.5 * (1 - (n % 730) / 730.0)), 2) AS monto
FROM (SELECT n, RANDOM() AS r1, RANDOM() AS r2 FROM nums WHERE n < 3000) t;

-- ---------- Gastos ficticios (~1,200 registros) ----------
INSERT INTO exec_dash.fact_gastos (fecha, categoria_id, descripcion, monto)
SELECT
    DATEADD(day, -((n * 3) % 730), CURRENT_DATE)::DATE                 AS fecha,
    CASE WHEN r1 < .42 THEN 1 WHEN r1 < .65 THEN 2 WHEN r1 < .80 THEN 3
         WHEN r1 < .90 THEN 4 ELSE 5 END                               AS categoria_id,
    'Gasto #' || n                                                     AS descripcion,
    ROUND((400 + r2 * 2000) * (0.8 + 0.4 * (1 - ((n * 3) % 730) / 730.0)), 2) AS monto
FROM (SELECT n, RANDOM() AS r1, RANDOM() AS r2 FROM nums WHERE n < 1200) t;

-- ---------- Actividad reciente ----------
INSERT INTO exec_dash.log_actividad (ts, tipo, titulo, detalle) VALUES
 (DATEADD(hour,  -2, GETDATE()), 'venta',   'Nueva venta registrada',   'Cliente: TechSolutions'),
 (DATEADD(hour,  -4, GETDATE()), 'pago',    'Pago recibido',            '$4,800 · Consultoría Premium'),
 (DATEADD(hour,  -6, GETDATE()), 'cliente', 'Nuevo cliente',            'Global Systems Inc.'),
 (DATEADD(hour,  -8, GETDATE()), 'reporte', 'Reporte mensual generado', 'Cierre del mes anterior'),
 (DATEADD(hour, -27, GETDATE()), 'venta',   'Nueva venta registrada',   'Cliente: Nova Retail');

ANALYZE exec_dash.fact_ingresos;
ANALYZE exec_dash.fact_gastos;
