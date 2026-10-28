# app/services/analyzer.py

import pandas as pd

def analyze_sales_data(df: pd.DataFrame):

    df = df.copy()

    # 🔥 Asegurar columna total
    df["total"] = df["quantity"] * df["price"]

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

    executive_summary = {
        "total_sold": float(total_sold),
        "total_transactions": int(total_transactions),
        "top_product": {
            "name": top_product,
            "revenue": float(top_product_value)
        },
        "best_month": {
            "month": str(best_month),
            "revenue": float(best_month_value)
        },
        "avg_ticket": float(avg_ticket)
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
        "top5_products_revenue": top5_revenue.to_dict(),
        "top5_products_quantity": top5_quantity.to_dict(),
        "top5_months": {str(k): float(v) for k, v in top5_months.items()}
    }

    # =========================
    # 3️⃣ TENDENCIA
    # =========================

    monthly_df = monthly_sales.reset_index()
    monthly_df["year_month"] = monthly_df["year_month"].astype(str)
    monthly_df["pct_change"] = monthly_df["total"].pct_change() * 100

    trend = monthly_df.fillna(0).to_dict(orient="records")

    # =========================
    # 4️⃣ INSIGHTS
    # =========================

    insights = generate_insights(product_revenue, monthly_sales, total_sold)

    return {
        "executive_summary": executive_summary,
        "rankings": rankings,
        "trend": trend,
        "insights": insights
    }

def generate_insights(product_revenue, monthly_sales, total_sold):

    insights = []

    # # Concentración Top 2
    # top2_share = product_revenue.head(2).sum() / total_sold

    # if top2_share > 0.4:
    #     insights.append(
    #         f"El {round(top2_share*100,1)}% de tus ingresos provienen de solo 2 productos."
    #     )

    top2 = product_revenue.head(2)
    top2_share = top2.sum() / total_sold

    if top2_share > 0.4:
        productos = ", ".join(top2.index.tolist())

        insights.append(
            f"El {round(top2_share*100,1)}% de tus ingresos provienen de solo 2 productos: {productos}."
        )

    # Crecimiento entre primer y último mes
    if len(monthly_sales) >= 2:
        first = monthly_sales.iloc[0]
        last = monthly_sales.iloc[-1]

        growth = (last - first) / first if first != 0 else 0

        if growth > 0:
            insights.append(
                f"Tus ventas crecieron {round(growth*100,1)}% entre el primer y último mes."
            )
        elif growth < 0:
            insights.append(
                f"Tus ventas cayeron {round(abs(growth)*100,1)}% en el periodo analizado."
            )

    return insights

    