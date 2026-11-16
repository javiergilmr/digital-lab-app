# app/services/pdf_report.py

import io
import math
import re
import unicodedata
from datetime import date
from xml.sax.saxutils import escape

from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

APP_NAME = "Data Cleaner & Sales Report"
TITLE_SUFFIX = "Sales Report"

# Misma paleta de clean.html
INK = HexColor("#111827")
MUTED = HexColor("#6b7280")
LINE = HexColor("#e5e7eb")
LINE_SOFT = HexColor("#f3f4f6")
ACCENT = HexColor("#0d6efd")

MARGIN = 0.8 * inch
# SimpleDocTemplate agrega 6 pt de relleno a cada lado del contenido
FRAME_PADDING = 6
LEFT_EDGE = MARGIN + FRAME_PADDING
RIGHT_EDGE = letter[0] - LEFT_EDGE
PAGE_WIDTH = RIGHT_EDGE - LEFT_EDGE

TITLE = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=INK)
SUBTITLE = ParagraphStyle("subtitle", fontName="Helvetica", fontSize=9, leading=12, textColor=MUTED)
HEADING = ParagraphStyle("heading", fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=MUTED, spaceAfter=8)
HERO = ParagraphStyle("hero", fontName="Helvetica-Bold", fontSize=28, leading=32, textColor=INK)
LABEL = ParagraphStyle("label", fontName="Helvetica", fontSize=8, leading=11, textColor=MUTED)
VALUE = ParagraphStyle("value", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=INK)
NOTE = ParagraphStyle("note", fontName="Helvetica", fontSize=8, leading=11, textColor=MUTED)
BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=10, leading=14, textColor=INK)
BODY_RIGHT = ParagraphStyle("body_right", parent=BODY, fontName="Helvetica-Bold", alignment=TA_RIGHT)
MUTED_RIGHT = ParagraphStyle("muted_right", parent=BODY, textColor=MUTED, alignment=TA_RIGHT)
LABEL_RIGHT = ParagraphStyle("label_right", parent=LABEL, alignment=TA_RIGHT)


def format_number(value):
    return f"{value:,.2f}"


def format_money(value):
    return ("-$" if value < 0 else "$") + format_number(abs(value))


def format_pct(value):
    return format_number(value) + "%"


def text(value, style):
    # Los nombres vienen del archivo subido y Paragraph interpreta el texto como marcado
    return Paragraph(escape(str(value)), style)


def section(*flowables):
    return KeepTogether([
        Spacer(1, 14),
        HRFlowable(width="100%", thickness=0.75, color=LINE, spaceAfter=14),
        *flowables,
    ])


def stat(label, value, note=None):
    cell = [text(label, LABEL), text(value, VALUE)]
    if note:
        cell.append(text(note, NOTE))
    return cell


def stats_table(summary, has_profit):
    rows = [[
        stat("Total transacciones", f"{summary['total_transactions']:,}"),
        stat("Ticket promedio", format_money(summary["avg_ticket"])),
        stat("Producto top", summary["top_product"]["name"], format_money(summary["top_product"]["revenue"])),
        stat("Mejor mes", summary["best_month"]["month"], format_money(summary["best_month"]["revenue"])),
    ]]
    if has_profit:
        rows.append([
            stat("Utilidad", format_money(summary["total_profit"])),
            stat("Margen", format_pct(summary["margin_pct"])),
            "",
            "",
        ])

    table = Table(rows, colWidths=[PAGE_WIDTH / 4] * 4)
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 1), (-1, -1), 12),
    ]))
    return table


def breakdown_table(title, rows, has_profit):
    """Categorías, tiendas o ciudades: ventas, % del total y, si hay costos, utilidad y margen."""
    header = [title, "Ventas", "% del total"] + (["Utilidad", "Margen"] if has_profit else [])
    data = [[text(h, LABEL if i == 0 else LABEL_RIGHT) for i, h in enumerate(header)]]
    for row in rows:
        cells = [text(row["name"], BODY), text(format_money(row["revenue"]), BODY_RIGHT),
                 text(format_pct(row["share_pct"]), MUTED_RIGHT)]
        if has_profit:
            cells += [text(format_money(row["profit"]), BODY_RIGHT), text(format_pct(row["margin_pct"]), MUTED_RIGHT)]
        data.append(cells)

    widths = [0.32, 0.18, 0.14, 0.18, 0.18] if has_profit else [0.5, 0.28, 0.22]
    table = Table(data, colWidths=[PAGE_WIDTH * w for w in widths], repeatRows=1)
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (1, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, LINE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.5, LINE_SOFT),
    ]))
    return table


def ranking_table(products):
    table = Table(
        [[text(name, BODY), text(format_money(value), BODY_RIGHT)] for name, value in products.items()],
        colWidths=[PAGE_WIDTH * 0.7, PAGE_WIDTH * 0.3],
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE_SOFT),
    ]))
    return table


def sales_chart(trend):
    months = [item for item in trend if item["total"] > 0]

    # Con muchos meses solo se rotula uno de cada N para que no se encimen
    step = math.ceil(len(months) / 12)
    labels = [item["year_month"] if i % step == 0 else "" for i, item in enumerate(months)]

    chart = HorizontalLineChart()
    chart.x = 72
    chart.y = 20
    chart.width = PAGE_WIDTH - 80
    chart.height = 160
    chart.data = [[item["total"] for item in months]]

    line = chart.lines[0]
    line.strokeColor = ACCENT
    line.strokeWidth = 1.5
    line.symbol = makeMarker("FilledCircle", size=5, fillColor=ACCENT, strokeColor=ACCENT)

    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.strokeColor = LINE
    chart.categoryAxis.visibleTicks = 0
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 7
    chart.categoryAxis.labels.fillColor = MUTED
    chart.categoryAxis.labels.boxAnchor = "n"
    chart.categoryAxis.labels.dy = -4

    chart.valueAxis.valueMin = 0
    chart.valueAxis.visibleAxis = 0
    chart.valueAxis.visibleTicks = 0
    chart.valueAxis.visibleGrid = 1
    chart.valueAxis.gridStrokeColor = LINE_SOFT
    chart.valueAxis.gridStrokeWidth = 0.75
    chart.valueAxis.labelTextFormat = format_money
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.labels.fillColor = MUTED

    drawing = Drawing(PAGE_WIDTH, 190)
    drawing.add(chart)
    return drawing


def draw_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(LEFT_EDGE, 0.5 * inch, f"© JAGM {APP_NAME} 2026. Todos los derechos reservados.")
    canvas.drawRightString(RIGHT_EDGE, 0.5 * inch, f"Página {doc.page}")
    canvas.restoreState()


def report_slug(report_name) -> str:
    # "Fridays Company" -> "fridays_company", para usarlo en los nombres de archivo
    name = re.sub(r"\.(pdf|csv)\s*$", "", report_name, flags=re.IGNORECASE)
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", name).strip("_")


def report_title(report_name) -> str:
    # "Fridays Company" -> "FRIDAYS COMPANY Sales Report"
    name = report_name.upper()
    if name.endswith(TITLE_SUFFIX.upper()):
        return name
    return f"{name} {TITLE_SUFFIX}"


def build_sales_report_pdf(analysis, report_name="") -> bytes:
    summary = analysis["executive_summary"]
    insights = analysis["insights"]
    has_sales = any(item["total"] > 0 for item in analysis["trend"])
    has_profit = analysis.get("has_profit", False)
    profit_ranking = analysis["rankings"].get("top5_products_profit") or {}

    title = report_title(report_name) if report_name else APP_NAME
    generated = f"Generado el {date.today():%Y-%m-%d}"

    story = [
        text(title, TITLE),
        Spacer(1, 2),
        text(f"{APP_NAME} · {generated}" if report_name else generated, SUBTITLE),
        section(
            text("Total vendido", HEADING),
            text(format_money(summary["total_sold"]), HERO),
            Spacer(1, 14),
            stats_table(summary, has_profit),
        ),
        section(
            text("Top 5 productos por ingresos", HEADING),
            ranking_table(analysis["rankings"]["top5_products_revenue"]),
        ),
    ]

    if profit_ranking:
        story.append(section(text("Top 5 productos por utilidad", HEADING), ranking_table(profit_ranking)))

    # Solo aparecen si el archivo trae categoría, tienda o ciudad
    for key, heading, column in [
        ("by_category", "Ventas por categoría", "Categoría"),
        ("by_store", "Ventas por tienda", "Tienda"),
        ("by_city", "Ventas por ciudad", "Ciudad"),
    ]:
        rows = analysis.get(key) or []
        if rows:
            story.append(section(text(heading, HEADING), breakdown_table(column, rows, has_profit)))

    if has_sales:
        story.append(section(text("Ventas mensuales", HEADING), sales_chart(analysis["trend"])))

    if insights:
        story.append(section(
            text("Insights", HEADING),
            *[text(insight, ParagraphStyle("insight", parent=BODY, spaceAfter=6)) for insight in insights],
        ))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=0.7 * inch,
        bottomMargin=0.8 * inch,
        title=title,
        author="JAGM Data Cleaner",
    )
    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return buffer.getvalue()
