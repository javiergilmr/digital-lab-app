# app/services/analyzer.py

import numpy as np
import pandas as pd

def to_decimal(value):
    return round(float(value), 2)

def share_pct(part, total):
    return to_decimal(part / total * 100) if total else 0.0

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

def format_money(value):
    return f"-${abs(value):,.2f}" if value < 0 else f"${value:,.2f}"

def plural(count, singular, plural_form):
    return f"{count:,} {singular if count == 1 else plural_form}"

def date_text(date, with_year=True):
    text = f"{date.day} de {MONTHS[date.month - 1]}"
    return f"{text} de {date.year}" if with_year else text

def month_text(period):
    return f"{MONTHS[period.month - 1]} de {period.year}"

def revenue_of(df):
    # La venta neta ya descuenta promociones; sin ella se usa cantidad × precio
    gross = df["quantity"] * df["price"]
    if "net_sales" in df.columns:
        return df["net_sales"].fillna(gross)
    return gross

def profit_of(df):
    if "profit" in df.columns:
        return df["profit"]
    if "total_cost" in df.columns:
        return df["total"] - df["total_cost"]
    if "unit_cost" in df.columns:
        return df["total"] - df["quantity"] * df["unit_cost"]
    return None

def breakdown(df, key, has_profit, label=None):
    """Ventas (y utilidad) por categoría, tienda o ciudad, de mayor a menor."""
    columns = {"revenue": ("total", "sum")}
    if has_profit:
        columns["profit"] = ("profit", "sum")
    grouped = df.groupby(key).agg(**columns).sort_values("revenue", ascending=False)

    total = grouped["revenue"].sum()
    rows = []
    for name, row in grouped.iterrows():
        item = {
            "name": label(name) if label else str(name),
            "revenue": to_decimal(row["revenue"]),
            "share_pct": share_pct(row["revenue"], total),
        }
        if has_profit:
            item["profit"] = to_decimal(row["profit"])
            item["margin_pct"] = share_pct(row["profit"], row["revenue"])
        rows.append(item)
    return rows

def analyze_sales_data(df: pd.DataFrame):

    df = df.copy()

    # 🔥 Ingreso por fila (venta neta si existe) y utilidad si hay datos de costo
    df["total"] = revenue_of(df)
    profit = profit_of(df)
    has_profit = profit is not None
    if has_profit:
        df["profit"] = profit

    # =========================
    # 1️⃣ RESUMEN EJECUTIVO
    # =========================

    total_sold = df["total"].sum()
    total_transactions = len(df)
    avg_ticket = total_sold / total_transactions if total_transactions else 0

    product_revenue = (
        df.groupby("product")["total"]
        .sum()
        .sort_values(ascending=False)
    )

    top_product = product_revenue.index[0]
    top_product_value = product_revenue.iloc[0]

    df["year_month"] = df["date"].dt.to_period("M")

    monthly_sales = (
        df.groupby("year_month")["total"]
        .sum()
        .sort_index()
    )

    best_month = monthly_sales.idxmax()
    best_month_value = monthly_sales.max()

    total_profit = df["profit"].sum() if has_profit else None

    executive_summary = {
        "total_sold": to_decimal(total_sold),
        "total_transactions": int(total_transactions),
        "top_product": {
            "name": top_product,
            "revenue": to_decimal(top_product_value)
        },
        "best_month": {
            "month": str(best_month),
            "revenue": to_decimal(best_month_value)
        },
        "avg_ticket": to_decimal(avg_ticket),
        "total_profit": to_decimal(total_profit) if has_profit else None,
        "margin_pct": share_pct(total_profit, total_sold) if has_profit else None
    }

    # =========================
    # 2️⃣ RANKINGS
    # =========================

    top5_revenue = product_revenue.head(5)

    top5_quantity = (
        df.groupby("product")["quantity"]
        .sum()
        .sort_values(ascending=False)
        .head(5)
    )

    top5_months = (
        monthly_sales
        .sort_values(ascending=False)
        .head(5)
    )

    rankings = {
        "top5_products_revenue": {k: to_decimal(v) for k, v in top5_revenue.items()},
        "top5_products_quantity": {k: to_decimal(v) for k, v in top5_quantity.items()},
        "top5_months": {str(k): to_decimal(v) for k, v in top5_months.items()},
        "top5_products_profit": {}
    }

    if has_profit:
        top5_profit = df.groupby("product")["profit"].sum().sort_values(ascending=False).head(5)
        rankings["top5_products_profit"] = {k: to_decimal(v) for k, v in top5_profit.items()}

    # =========================
    # 3️⃣ TENDENCIA
    # =========================

    monthly_df = monthly_sales.reset_index()
    monthly_df["year_month"] = monthly_df["year_month"].astype(str)
    monthly_df["total"] = monthly_df["total"].astype(float)
    # Un mes en $0 seguido de ventas daría infinito, que no se puede enviar como JSON
    monthly_df["pct_change"] = (monthly_df["total"].pct_change() * 100).replace([np.inf, -np.inf], np.nan)

    trend = monthly_df.fillna(0).round(2).to_dict(orient="records")

    # =========================
    # 4️⃣ DESGLOSES (solo si el archivo trae esas columnas)
    # =========================

    by_category = breakdown(df, "category", has_profit) if "category" in df.columns else []

    by_store = []
    by_city = []
    if "store_id" in df.columns:
        cities = df.groupby("store_id")["store_city"].first() if "store_city" in df.columns else {}
        by_store = breakdown(
            df, "store_id", has_profit,
            label=lambda s: f"{s} · {cities[s]}" if s in cities and pd.notna(cities[s]) else str(s)
        )
    if "store_city" in df.columns:
        # Con una tienda por ciudad, el desglose por ciudad repetiría el de tiendas
        if "store_id" not in df.columns or df["store_city"].nunique() < df["store_id"].nunique():
            by_city = breakdown(df, "store_city", has_profit)

    # =========================
    # 5️⃣ DESCRIPCIÓN DEL INFORME
    # =========================

    overview = build_overview(df, executive_summary, best_month, monthly_sales, has_profit)

    # =========================
    # 6️⃣ INSIGHTS
    # =========================

    insights = generate_insights(product_revenue, monthly_sales, total_sold, by_category, by_store, has_profit)

    return {
        "overview": overview,
        "executive_summary": executive_summary,
        "rankings": rankings,
        "trend": trend,
        "by_category": by_category,
        "by_store": by_store,
        "by_city": by_city,
        "has_profit": has_profit,
        "insights": insights
    }

def build_overview(df, summary, best_month, monthly_sales, has_profit):
    """Párrafo que presenta el informe (alcance, periodo y resultado) y nota de cómo se calculó."""
    start, end = df["date"].min(), df["date"].max()
    if start.date() == end.date():
        period = f"el {date_text(start)}"
    else:
        period = f"entre el {date_text(start, start.year != end.year)} y el {date_text(end)}"

    scope = [plural(df["product"].nunique(), "producto", "productos")]
    if "category" in df.columns:
        scope.append(plural(df["category"].nunique(), "categoría", "categorías"))
    if "store_id" in df.columns:
        scope.append(plural(df["store_id"].nunique(), "tienda", "tiendas"))
    scope_text = ", ".join(scope[:-1]) + f" y {scope[-1]}" if len(scope) > 1 else scope[0]

    months = len(monthly_sales)
    text = (
        f"Este informe resume {plural(summary['total_transactions'], 'transacción registrada', 'transacciones registradas')} "
        f"{period} ({plural(months, 'mes', 'meses')}), con {scope_text}. "
        f"En el periodo se vendieron {format_money(summary['total_sold'])}"
    )
    if has_profit:
        text += (
            f", con una utilidad de {format_money(summary['total_profit'])} "
            f"y un margen de {summary['margin_pct']:.2f}%"
        )
    text += f". El producto con más ingresos fue {summary['top_product']['name']}"
    text += f" y el mejor mes, {month_text(best_month)}." if months > 1 else "."

    notes = []
    if "net_sales" in df.columns:
        notes.append("Las ventas corresponden a la venta neta, después de descuentos.")
    else:
        notes.append("Las ventas se calculan como cantidad × precio unitario.")
    if has_profit:
        notes.append("La utilidad es la venta menos el costo, y el margen es la utilidad sobre las ventas.")
    notes.append("Los datos se limpiaron antes del análisis; el detalle está al final del informe.")

    return {"text": text, "note": " ".join(notes)}

def generate_insights(product_revenue, monthly_sales, total_sold, by_category, by_store, has_profit):

    insights = []

    # # Concentración Top 2
    # top2_share = product_revenue.head(2).sum() / total_sold

    # if top2_share > 0.4:
    #     insights.append(
    #         f"El {round(top2_share*100,1)}% de tus ingresos provienen de solo 2 productos."
    #     )

    top2 = product_revenue.head(2)
    top2_share = top2.sum() / total_sold if total_sold else 0

    if len(top2) == 2 and top2_share > 0.4:
        productos = ", ".join(top2.index.tolist())

        insights.append(
            f"El {top2_share*100:.2f}% de tus ingresos provienen de solo 2 productos: {productos}."
        )

    # Crecimiento entre primer y último mes
    if len(monthly_sales) >= 2:
        first = monthly_sales.iloc[0]
        last = monthly_sales.iloc[-1]

        growth = (last - first) / first if first != 0 else 0

        if growth > 0:
            insights.append(
                f"Tus ventas crecieron {growth*100:.2f}% entre el primer y último mes."
            )
        elif growth < 0:
            insights.append(
                f"Tus ventas cayeron {abs(growth)*100:.2f}% en el periodo analizado."
            )

    # Categorías: la que más utilidad deja y la de menor margen
    if has_profit and len(by_category) >= 2:
        best = max(by_category, key=lambda c: c["profit"])
        total_profit = sum(c["profit"] for c in by_category)
        if total_profit > 0:
            insights.append(
                f"«{best['name']}» es la categoría que más utilidad deja: {best['profit'] / total_profit * 100:.2f}% del total."
            )

        lowest = min(by_category, key=lambda c: c["margin_pct"])
        if lowest["name"] != best["name"]:
            insights.append(
                f"«{lowest['name']}» tiene el margen más bajo ({lowest['margin_pct']:.2f}%): revisa precios o costos."
            )

    # Tiendas: la que más vende
    if len(by_store) >= 2:
        top_store = by_store[0]
        insights.append(
            f"La tienda con más ventas es {top_store['name']}, con el {top_store['share_pct']:.2f}% del total."
        )

    return insights
