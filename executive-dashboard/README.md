# Executive Dashboard

Dashboard ejecutivo minimalista en un solo `.html`, responsivo (web + móvil), con datos ficticios que imitan exactamente la salida de consultas SQL en Amazon Redshift.

## Estructura

```
executive-dashboard/
├── dashboard.html            # Dashboard (web + móvil, modo claro/oscuro)
├── api.py                    # API Flask: ejecuta las consultas y devuelve JSON
└── sql/
    ├── 01_schema_seed.sql    # Esquema exec_dash + datos ficticios (24 meses)
    └── 02_queries.sql        # Consultas que alimentan cada widget
```

## Modos de datos

| Modo | Cómo | Fuente |
|------|------|--------|
| Demo | Abrir `dashboard.html` | Datos ficticios generados en el navegador |
| SQL  | `dashboard.html?api=http://localhost:5000/api/dashboard` | Redshift vía `api.py` |

Si la API falla, el dashboard vuelve solo a modo demo y lo indica en la barra lateral.

## Contrato de datos (JSON)

```json
{
  "ingresos_categoria": [{"mes": "2026-10", "categoria": "Ventas", "ingresos": 62340}],
  "gastos_categoria":   [{"mes": "2026-10", "categoria": "Personal", "gastos": 33380}],
  "ingresos_producto":  [{"mes": "2026-10", "producto": "Consultoría Premium", "categoria": "Servicios", "ingresos": 24800}],
  "actividad":          [{"ts": "2026-10-27T16:00:00", "tipo": "venta", "titulo": "Nueva venta registrada", "detalle": "Cliente: TechSolutions"}]
}
```

KPIs (ingresos, gastos, utilidad, margen y variaciones) se calculan en el navegador a partir de estos datasets; `kpis_mensuales` en `02_queries.sql` (y `/api/kpis`) sirve para validar los mismos números en SQL.

## Puesta en marcha con Redshift

1. Ejecutar `sql/01_schema_seed.sql` en Redshift.
2. `pip install flask flask-cors redshift_connector`
3. Definir `REDSHIFT_HOST`, `REDSHIFT_USER`, `REDSHIFT_PASSWORD` (opcional `REDSHIFT_DB`, `REDSHIFT_PORT`).
4. `python api.py`
5. Abrir `dashboard.html?api=http://localhost:5000/api/dashboard`.
