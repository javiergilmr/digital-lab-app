"""
Executive Dashboard · servidor local
====================================
Sirve dashboard.html y una API que consulta la base de datos con SQL.

  python server.py                      # Olist (data/olist.db, creada con load_olist.py)
  python server.py --dataset demo       # SQLite ficticia (sin descargar nada)
  python server.py --dataset demo --reset   # regenera la base ficticia
  python server.py --backend redshift   # Amazon Redshift (pip install redshift_connector)

Luego abre http://localhost:8000

Endpoints:
  GET  /api/dashboard       datasets del dashboard (sql/<backend>/02_queries.sql)
  GET  /api/kpis            KPI mensuales calculados en SQL (validación)
  POST /api/simular-venta   inserta una venta aleatoria (demostración en vivo)

Redshift usa: REDSHIFT_HOST, REDSHIFT_USER, REDSHIFT_PASSWORD,
              REDSHIFT_DB (default dev), REDSHIFT_PORT (default 5439)
"""
import argparse
import datetime
import decimal
import json
import os
import random
import re
import sqlite3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
FUENTES = {
    "demo": {
        "db": os.path.join(BASE, "data", "exec_dash.db"),
        "label": "SQLite · datos ficticios",
        "empresa": "Acme Corp", "moneda": "$", "readonly": False, "gastos_modelados": False,
    },
    "olist": {
        "db": os.path.join(BASE, "data", "olist.db"),
        "label": "Olist · datos reales",
        "empresa": "Olist Store", "moneda": "R$", "readonly": True, "gastos_modelados": True,
        "atribucion": "Olist · Brazilian E-Commerce Public Dataset (CC BY-NC-SA 4.0)",
    },
}
DATASETS = ["ingresos_categoria", "gastos_categoria", "ingresos_producto", "actividad"]
# Se ejecutan solo si existen en 02_queries.sql (el dashboard funciona sin ellos)
DATASETS_OPCIONALES = ["resumen_mensual", "supuestos_gastos", "resumen_categoria", "gastos_por_categoria_ingreso",
                       "resumen_producto", "gastos_por_producto"]
OLIST_FALTA = ("No existe data/olist.db. Para ver datos reales de Olist:\n"
               "1. Descarga https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce\n"
               "2. Descomprime los CSV en data/raw/olist/\n"
               "3. python load_olist.py")
META_KEYS = ("empresa", "moneda", "readonly", "gastos_modelados", "atribucion")
CLIENTES = ["TechSolutions", "Nova Retail", "Global Systems Inc.", "Andes Logistics",
            "Pacific Foods", "Grupo Istmo", "BlueWave Media", "Canal Partners"]
PRODUCTOS = {1: "Desarrollo de Software", 2: "Implementaciones", 3: "Consultoría Premium",
             4: "Soporte Técnico", 5: "Licencias", 6: "Hosting", 7: "Capacitación", 8: "Auditoría"}


def load_queries(backend):
    path = os.path.join(BASE, "sql", backend, "02_queries.sql")
    with open(path, encoding="utf-8") as f:
        parts = re.split(r"^--\s*name:\s*(\w+)\s*$", f.read(), flags=re.M)
    return {parts[i]: parts[i + 1].strip().rstrip(";") for i in range(1, len(parts), 2)}


def to_json(v):
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    return v


# ---------------------------------------------------------------- backends
class SQLiteBackend:
    name = "sqlite"

    def __init__(self, dataset="demo", reset=False):
        cfg = FUENTES[dataset]
        self.path, self.label = cfg["db"], cfg["label"]
        self.meta = {k: cfg[k] for k in META_KEYS if k in cfg}
        if dataset == "olist":
            # Sin olist.db la API responde error y el dashboard muestra su muestra con forma de Olist.
            # Se revisa en cada petición: basta con correr load_olist.py, sin reiniciar el servidor.
            if not os.path.exists(self.path):
                print("Aviso: " + OLIST_FALTA.replace("\n", "\n  "))
            return
        if reset and os.path.exists(self.path):
            os.remove(self.path)
        if not os.path.exists(self.path):
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            conn = sqlite3.connect(self.path)
            for script in ("00_schema.sql", "01_seed_demo.sql"):
                with open(os.path.join(BASE, "sql", "sqlite", script), encoding="utf-8") as f:
                    conn.executescript(f.read())
            conn.commit()
            conn.close()
            print(f"Base ficticia creada en {self.path}")

    def connect(self):
        if not os.path.exists(self.path):
            raise FileNotFoundError(OLIST_FALTA)
        return sqlite3.connect(self.path)

    def insert_sale(self, conn, cliente, producto_id, monto, detalle):
        conn.execute("INSERT INTO fact_ingresos (fecha, cliente, producto_id, monto) "
                     "VALUES (date('now','localtime'), ?, ?, ?)", (cliente, producto_id, monto))
        conn.execute("INSERT INTO log_actividad (ts, tipo, titulo, detalle) "
                     "VALUES (strftime('%Y-%m-%dT%H:%M:%SZ','now'), 'venta', 'Nueva venta registrada', ?)",
                     (detalle,))


class RedshiftBackend:
    name, label = "redshift", "Amazon Redshift · exec_dash"
    meta = {"empresa": "Acme Corp", "moneda": "$", "readonly": False, "gastos_modelados": False}

    def __init__(self, reset=False):
        import redshift_connector  # noqa: F401  (falla temprano si no está instalado)

    def connect(self):
        import redshift_connector
        return redshift_connector.connect(
            host=os.environ["REDSHIFT_HOST"],
            database=os.environ.get("REDSHIFT_DB", "dev"),
            port=int(os.environ.get("REDSHIFT_PORT", 5439)),
            user=os.environ["REDSHIFT_USER"],
            password=os.environ["REDSHIFT_PASSWORD"],
        )

    def insert_sale(self, conn, cliente, producto_id, monto, detalle):
        cur = conn.cursor()
        cur.execute("INSERT INTO exec_dash.fact_ingresos (fecha, cliente, producto_id, monto) "
                    "VALUES (CURRENT_DATE, %s, %s, %s)", (cliente, producto_id, monto))
        cur.execute("INSERT INTO exec_dash.log_actividad (ts, tipo, titulo, detalle) "
                    "VALUES (GETDATE(), 'venta', 'Nueva venta registrada', %s)", (detalle,))


def run_query(backend, conn, sql):
    cur = conn.cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    return [{c: to_json(v) for c, v in zip(cols, row)} for row in cur.fetchall()]


# ---------------------------------------------------------------- HTTP
class Handler(SimpleHTTPRequestHandler):
    backend = None

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=BASE, **kw)

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self.path = "/dashboard.html"
            return super().do_GET()
        if path == "/api/dashboard":
            return self.api(self.dashboard)
        if path == "/api/kpis":
            return self.api(lambda conn: run_query(self.backend, conn, load_queries(self.backend.name)["kpis_mensuales"]))
        if path.startswith("/data/") or path.endswith((".py", ".db")):
            return self.send_error(404)
        return super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] == "/api/simular-venta":
            return self.api(self.simulate_sale)
        self.send_error(404)

    def api(self, fn):
        try:
            conn = self.backend.connect()
            try:
                return self.send_json(fn(conn))
            finally:
                conn.close()
        except Exception as e:  # noqa: BLE001
            return self.send_json({"error": str(e)}, 500)

    def dashboard(self, conn):
        q = load_queries(self.backend.name)
        out = {k: run_query(self.backend, conn, q[k]) for k in DATASETS + DATASETS_OPCIONALES if k in q}
        out["meta"] = {"backend": self.backend.name, "label": self.backend.label,
                       "generado": datetime.datetime.now().isoformat(timespec="seconds"),
                       **self.backend.meta}
        return out

    def simulate_sale(self, conn):
        if self.backend.meta.get("readonly"):
            raise PermissionError("Este dataset es de solo lectura (datos reales).")
        cliente = random.choice(CLIENTES)
        producto_id = random.choice(list(PRODUCTOS))
        monto = round(random.uniform(800, 4500), 2)
        detalle = f"{cliente} · {PRODUCTOS[producto_id]} · ${monto:,.0f}"
        self.backend.insert_sale(conn, cliente, producto_id, monto, detalle)
        conn.commit()
        return {"ok": True, "cliente": cliente, "producto": PRODUCTOS[producto_id], "monto": monto}

    def log_message(self, fmt, *args):
        if "/api/" in self.path:
            super().log_message(fmt, *args)


def main():
    ap = argparse.ArgumentParser(description="Executive Dashboard · servidor local")
    ap.add_argument("--backend", choices=["sqlite", "redshift"], default=os.environ.get("DB_BACKEND", "sqlite"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    ap.add_argument("--dataset", choices=list(FUENTES), default=os.environ.get("DATASET", "olist"),
                    help="con SQLite: olist (dataset público, por defecto) o demo (ficticio)")
    ap.add_argument("--reset", action="store_true", help="regenerar la base ficticia SQLite")
    args = ap.parse_args()

    Handler.backend = SQLiteBackend(args.dataset, args.reset) if args.backend == "sqlite" else RedshiftBackend()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Executive Dashboard → http://localhost:{args.port}   (base: {Handler.backend.label})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")


if __name__ == "__main__":
    main()
