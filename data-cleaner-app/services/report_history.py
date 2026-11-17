# Historial de informes del panel: cada archivo procesado guarda un resumen en la tabla reports
# y su PDF en el bucket privado "reports" de Supabase Storage (ver supabase/reports.sql)

import logging
import uuid
from datetime import datetime

from services.pdf_report import build_sales_report_pdf, report_slug
from services.supabase_auth import AuthError, rest_call, storage_download, storage_upload

log = logging.getLogger(__name__)

BUCKET = "reports"
HISTORY_LIMIT = 10


class HistoryUnavailable(Exception):
    pass


def save_report(access_token, user_id, file_name, report_name, clean_report, analysis):
    """Genera el PDF, lo sube y registra el informe. Si algo falla, solo se avisa en consola."""
    report_id = str(uuid.uuid4())
    pdf_path = f"{user_id}/{report_id}.pdf"

    try:
        pdf = build_sales_report_pdf(analysis, report_name)
        storage_upload(BUCKET, pdf_path, pdf, "application/pdf", access_token)
    except AuthError as e:
        # Sin PDF el informe igual aparece en el historial, solo que sin botón de descarga
        log.warning(f"No se pudo guardar el PDF del informe: {e}")
        pdf_path = None

    summary = analysis["executive_summary"]
    try:
        rest_call("POST", "/reports", {
            "id": report_id,
            "user_id": user_id,
            "report_name": report_name,
            "file_name": file_name,
            "rows_initial": clean_report["rows_initial"],
            "rows_final": clean_report["rows_final"],
            "rows_fixed": clean_report["rows_fixed"],
            "rows_removed": clean_report["rows_removed"],
            "total_sold": summary["total_sold"],
            "total_profit": summary["total_profit"],
            "margin_pct": summary["margin_pct"],
            "pdf_path": pdf_path,
        }, token=access_token)
    except AuthError as e:
        log.warning(f"No se pudo guardar el informe en el historial: {e}")


def list_reports(access_token, limit=HISTORY_LIMIT):
    """Últimos informes del usuario del token (RLS solo devuelve los suyos)."""
    try:
        return rest_call("GET", "/reports", token=access_token, query={
            "select": "id,created_at,report_name,file_name,rows_final,rows_fixed,rows_removed,"
                      "total_sold,total_profit,margin_pct,pdf_path",
            "order": "created_at.desc",
            "limit": limit,
        })
    except AuthError as e:
        log.warning(f"No se pudo leer el historial de informes: {e}")
        raise HistoryUnavailable() from None


def get_report_pdf(access_token, report_id):
    """(nombre de archivo, bytes) del PDF de un informe propio, o None si no existe o no tiene PDF."""
    try:
        uuid.UUID(report_id)
        rows = rest_call("GET", "/reports", token=access_token, query={
            "select": "report_name,created_at,pdf_path",
            "id": f"eq.{report_id}",
        })
    except (ValueError, AuthError):
        return None
    if not rows or not rows[0]["pdf_path"]:
        return None

    row = rows[0]
    try:
        pdf = storage_download(BUCKET, row["pdf_path"], access_token)
    except AuthError as e:
        log.warning(f"No se pudo descargar el PDF del informe: {e}")
        return None

    # Mismo nombre que la descarga original, con la fecha local en que se generó el informe
    day = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")).astimezone().date()
    slug = report_slug(row["report_name"])
    filename = f"{slug}_report_{day}.pdf" if slug else f"reporte_ventas_{day}.pdf"
    return filename, pdf
