"""
Carga el dataset público de Olist (e-commerce de Brasil, Kaggle) en
data/olist.db, con el mismo modelo que usa el dashboard.

  1. Descarga: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
  2. Descomprime los CSV en  data/raw/olist/
  3. python load_olist.py
  4. python server.py --dataset olist

Opciones:
  --src <carpeta>   carpeta con los CSV (default: data/raw/olist)

Qué es real y qué es modelado:
  - Ingresos, categorías, clientes, fechas, fletes y reseñas: datos reales.
  - Gastos: Olist no publica costos, se modelan con los SUPUESTOS de abajo.
"""
import argparse
import csv
import os
import sqlite3
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "data", "olist.db")
SRC_DEFAULT = os.path.join(BASE, "data", "raw", "olist")
SCHEMA = os.path.join(BASE, "sql", "sqlite", "00_schema.sql")

# El dataset va de sep-2016 a oct-2018, pero los extremos tienen muy pocas
# órdenes y distorsionarían tendencias y variaciones. Se usan meses completos.
INICIO, FIN = "2017-01-01", "2018-08-31"

ARCHIVOS = {
    "orders":    ("olist_orders_dataset.csv", True),
    "items":     ("olist_order_items_dataset.csv", True),
    "products":  ("olist_products_dataset.csv", True),
    "customers": ("olist_customers_dataset.csv", True),
    "reviews":   ("olist_order_reviews_dataset.csv", False),   # opcional
}

# ---------------------------------------------------------------- supuestos
# m = totales del mes: {"precio": suma de precios, "flete": suma de fletes}
SUPUESTOS = [
    ("Costo de mercancía", lambda m: 0.60 * m["precio"],                "60% del precio de venta"),
    ("Logística",          lambda m: m["flete"],                        "Flete real de cada pedido (dato real)"),
    ("Marketing",          lambda m: 0.07 * m["precio"],                "7% del precio de venta"),
    ("Comisiones de pago", lambda m: 0.025 * (m["precio"] + m["flete"]), "2.5% de lo cobrado"),
    ("Operaciones",        lambda m: 25000.0,                           "Costo fijo de R$25,000 al mes"),
]

# ---------------------------------------------------------------- categorías
# Olist tiene ~70 categorías en portugués. Se agrupan en 5 macro-categorías
# (nivel "categoría" del dashboard) y cada categoría original es un "producto".
MACRO = [
    ("Hogar y muebles", ("cama_", "moveis", "utilidades_domesticas", "casa_", "eletrodomesticos",
                         "eletroportateis", "climatizacao", "la_cuisine", "portateis_")),
    ("Tecnología",      ("informatica", "telefonia", "eletronicos", "consoles", "pc", "audio",
                         "tablets", "cine_foto")),
    ("Salud y belleza", ("beleza", "perfumaria", "fraldas", "bebes")),
    ("Moda y ocio",     ("esporte", "fashion", "relogios", "malas", "brinquedos", "cool_stuff",
                         "instrumentos", "livros", "artes", "papelaria", "musica", "cds", "dvds",
                         "artigos_de_festas", "artigos_de_natal", "flores")),
]
OTROS = "Otros"

NOMBRES = {
    "cama_mesa_banho": "Cama, mesa y baño", "beleza_saude": "Belleza y salud",
    "relogios_presentes": "Relojes y regalos", "esporte_lazer": "Deporte y ocio",
    "informatica_acessorios": "Informática", "moveis_decoracao": "Muebles y decoración",
    "utilidades_domesticas": "Artículos para el hogar", "cool_stuff": "Artículos novedosos",
    "automotivo": "Automotriz", "ferramentas_jardim": "Herramientas y jardín",
    "brinquedos": "Juguetes", "bebes": "Bebés", "perfumaria": "Perfumería",
    "telefonia": "Telefonía", "moveis_escritorio": "Muebles de oficina",
    "papelaria": "Papelería", "pet_shop": "Mascotas", "pcs": "Computadoras",
    "instrumentos_musicais": "Instrumentos musicales", "eletronicos": "Electrónica",
    "eletroportateis": "Pequeños electrodomésticos", "eletrodomesticos": "Electrodomésticos",
    "eletrodomesticos_2": "Electrodomésticos", "consoles_games": "Consolas y videojuegos",
    "fashion_bolsas_e_acessorios": "Bolsos y accesorios", "malas_acessorios": "Maletas",
    "construcao_ferramentas_construcao": "Herramientas de construcción",
    "casa_construcao": "Construcción del hogar", "climatizacao": "Climatización",
    "moveis_sala": "Muebles de sala", "alimentos": "Alimentos", "bebidas": "Bebidas",
    "audio": "Audio", "livros_interesse_geral": "Libros", "telefonia_fixa": "Telefonía fija",
    "agro_industria_e_comercio": "Agroindustria", "industria_comercio_e_negocios": "Industria y negocios",
    "market_place": "Marketplace", "moveis_cozinha_area_de_servico_jantar_e_jardim": "Muebles de cocina y jardín",
}


def macro_de(cat):
    for nombre, prefijos in MACRO:
        if cat.startswith(prefijos):
            return nombre
    return OTROS


def nombre_de(cat):
    if not cat:
        return "Sin categoría"
    return NOMBRES.get(cat, cat.replace("_", " ").capitalize())


# ---------------------------------------------------------------- lectura
def verificar(src):
    faltan = [f for f, req in ARCHIVOS.values() if req and not os.path.exists(os.path.join(src, f))]
    if faltan:
        sys.exit(f"\nNo encuentro estos archivos en {src}:\n  - " + "\n  - ".join(faltan) +
                 "\n\nDescarga el dataset de https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce"
                 "\ny descomprime los CSV en esa carpeta (o usa --src <carpeta>).")


def leer(src, clave):
    archivo, _ = ARCHIVOS[clave]
    path = os.path.join(src, archivo)
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def iso(ts):
    return ts.replace(" ", "T") if ts else ts


# ---------------------------------------------------------------- carga
def main():
    ap = argparse.ArgumentParser(description="Carga el dataset de Olist en data/olist.db")
    ap.add_argument("--src", default=SRC_DEFAULT, help="carpeta con los CSV de Olist")
    src = ap.parse_args().src
    verificar(src)

    print("Leyendo pedidos…")
    pedidos = {}                      # order_id -> {ts, customer_id}
    descartados = 0
    for r in leer(src, "orders"):
        ts = r["order_purchase_timestamp"]
        if r["order_status"] in ("canceled", "unavailable") or not (INICIO <= ts[:10] <= FIN):
            descartados += 1
            continue
        pedidos[r["order_id"]] = {"ts": ts, "customer_id": r["customer_id"], "total": 0.0, "cat": None}

    clientes = {r["customer_id"]: r for r in leer(src, "customers")}
    productos = {r["product_id"]: (r["product_category_name"] or "").strip() for r in leer(src, "products")}

    # Dimensiones: macro-categorías e "productos" (= categoría original de Olist)
    macros = [m for m, _ in MACRO] + [OTROS]
    macro_id = {m: i + 1 for i, m in enumerate(macros)}
    dim_producto = {}                 # categoría olist -> (id, nombre, macro_id)

    def producto_id(cat):
        if cat not in dim_producto:
            dim_producto[cat] = (len(dim_producto) + 1, nombre_de(cat), macro_id[macro_de(cat)])
        return dim_producto[cat][0]

    print("Leyendo líneas de pedido…")
    ingresos = []
    mensual = defaultdict(lambda: defaultdict(lambda: {"precio": 0.0, "flete": 0.0}))   # mes -> producto_id -> totales
    for r in leer(src, "items"):
        p = pedidos.get(r["order_id"])
        if not p:
            continue
        cat = productos.get(r["product_id"], "")
        precio, flete = float(r["price"]), float(r["freight_value"])
        c = clientes.get(p["customer_id"], {})
        pid = producto_id(cat)
        ingresos.append((p["ts"][:10], c.get("customer_unique_id"), pid, round(precio + flete, 2)))
        m = mensual[p["ts"][:7]][pid]
        m["precio"] += precio
        m["flete"] += flete
        p["total"] += precio + flete
        p["cat"] = p["cat"] or cat

    # Gastos modelados: una fila por mes, categoría de gasto y producto (categoría Olist),
    # con su macro-categoría para filtrar a ese nivel. La parte variable de cada supuesto
    # se calcula con el precio y el flete del producto; la parte fija (ej. Operaciones) se
    # reparte según su participación en los ingresos del mes. La suma por mes es la misma
    # que con los totales.
    macro_de_pid = {pid: mid for pid, _, mid in dim_producto.values()}
    gastos = []
    for mes, por_producto in sorted(mensual.items()):
        total_mes = sum(m["precio"] + m["flete"] for m in por_producto.values())
        for i, (nombre, calc, desc) in enumerate(SUPUESTOS, start=1):
            fijo = calc({"precio": 0.0, "flete": 0.0})
            for pid, m in sorted(por_producto.items()):
                share = (m["precio"] + m["flete"]) / total_mes if total_mes else 0
                gastos.append((mes + "-01", i, macro_de_pid[pid], pid, desc, round(calc(m) - fijo + fijo * share, 2)))

    # Actividad: últimos pedidos y últimas reseñas negativas del periodo
    actividad = []
    ultimos = sorted((p for p in pedidos.values() if p["total"] > 0), key=lambda p: p["ts"], reverse=True)[:3]
    for p in ultimos:
        c = clientes.get(p["customer_id"], {})
        lugar = f"{c.get('customer_city', '').title()}, {c.get('customer_state', '')}".strip(", ")
        actividad.append((iso(p["ts"]), "venta", "Nueva venta registrada",
                          f"{lugar} · {nombre_de(p['cat'])} · R${p['total']:,.0f}"))
    resenas = [r for r in leer(src, "reviews")
               if r["order_id"] in pedidos and r["review_score"] in ("1", "2")
               and r["review_creation_date"][:10] <= FIN]
    for r in sorted(resenas, key=lambda r: r["review_creation_date"], reverse=True)[:3]:
        texto = (r.get("review_comment_title") or r.get("review_comment_message") or "Sin comentario").strip()
        texto = texto if len(texto) <= 60 else texto[:57] + "…"
        cat = nombre_de(pedidos[r["order_id"]]["cat"])
        actividad.append((iso(r["review_creation_date"]), "resena", f"Reseña de {r['review_score']} estrella" +
                          ("s" if r["review_score"] != "1" else ""), f"{cat} · “{texto}”"))

    # Escribir la base
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.executemany("INSERT INTO dim_categoria_ingreso VALUES (?, ?)", [(i, m) for m, i in macro_id.items()])
    conn.executemany("INSERT INTO dim_categoria_gasto VALUES (?, ?)",
                     [(i, n) for i, (n, _, _) in enumerate(SUPUESTOS, start=1)])
    conn.executemany("INSERT INTO dim_producto VALUES (?, ?, ?)", list(dim_producto.values()))
    conn.executemany("INSERT INTO fact_ingresos (fecha, cliente, producto_id, monto) VALUES (?, ?, ?, ?)", ingresos)
    conn.executemany("INSERT INTO fact_gastos (fecha, categoria_id, categoria_ingreso_id, producto_id, descripcion, monto) "
                     "VALUES (?, ?, ?, ?, ?, ?)", gastos)
    conn.executemany("INSERT INTO log_actividad (ts, tipo, titulo, detalle) VALUES (?, ?, ?, ?)", actividad)
    conn.commit()
    conn.close()

    total = sum(r[3] for r in ingresos)
    print(f"\nListo: {DB_PATH}")
    print(f"  Pedidos cargados : {len(pedidos):,}  (descartados: {descartados:,} cancelados o fuera de {INICIO} a {FIN})")
    print(f"  Líneas de venta  : {len(ingresos):,}  ·  Ingresos: R${total:,.0f}")
    print(f"  Meses            : {len(mensual)}  ·  Categorías Olist: {len(dim_producto)}")
    print("\nSiguiente paso:  python server.py --dataset olist")


if __name__ == "__main__":
    main()
