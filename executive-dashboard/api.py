"""
API mínima para el Executive Dashboard.
Ejecuta las consultas de sql/02_queries.sql en Amazon Redshift y devuelve
el JSON que consume dashboard.html.

Instalación:
    pip install flask flask-cors redshift_connector

Variables de entorno:
    REDSHIFT_HOST, REDSHIFT_USER, REDSHIFT_PASSWORD
    REDSHIFT_DB (default: dev), REDSHIFT_PORT (default: 5439)

Uso:
    python api.py
    -> abre dashboard.html?api=http://localhost:5000/api/dashboard
"""
import datetime
import decimal
import os
import re

import redshift_connector
from flask import Flask, jsonify
from flask_cors import CORS

BASE = os.path.dirname(os.path.abspath(__file__))
QUERIES_FILE = os.path.join(BASE, "sql", "02_queries.sql")
DATASETS = ["ingresos_categoria", "gastos_categoria", "ingresos_producto", "actividad"]

app = Flask(__name__)
CORS(app)


def load_queries():
    """Separa el archivo por bloques '-- name: <clave>'."""
    with open(QUERIES_FILE, encoding="utf-8") as f:
        text = f.read()
    parts = re.split(r"^--\s*name:\s*(\w+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip().rstrip(";") for i in range(1, len(parts), 2)}


def to_json(v):
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    return v


def connect():
    return redshift_connector.connect(
        host=os.environ["REDSHIFT_HOST"],
        database=os.environ.get("REDSHIFT_DB", "dev"),
        port=int(os.environ.get("REDSHIFT_PORT", 5439)),
        user=os.environ["REDSHIFT_USER"],
        password=os.environ["REDSHIFT_PASSWORD"],
    )


@app.get("/api/dashboard")
def dashboard():
    queries = load_queries()
    out = {}
    conn = connect()
    try:
        cur = conn.cursor()
        for key in DATASETS:
            cur.execute(queries[key])
            cols = [d[0] for d in cur.description]
            out[key] = [{c: to_json(v) for c, v in zip(cols, row)} for row in cur.fetchall()]
    finally:
        conn.close()
    return jsonify(out)


@app.get("/api/kpis")
def kpis():
    """Endpoint de validación: KPI mensuales calculados en SQL."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(load_queries()["kpis_mensuales"])
        cols = [d[0] for d in cur.description]
        return jsonify([{c: to_json(v) for c, v in zip(cols, row)} for row in cur.fetchall()])
    finally:
        conn.close()


if __name__ == "__main__":
    app.run(port=5000, debug=True)
