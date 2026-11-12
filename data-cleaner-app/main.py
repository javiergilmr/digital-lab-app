from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
import pandas as pd
from services.column_validator import detect_sales_columns, validate_sales_file, validate_column_types
from services.schema import SALES_SCHEMA
from routers.api import router as api_router

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.include_router(api_router, prefix="/api")

from routers.pages import router as pages_router
from routers.auth import router as auth_router

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(pages_router)
app.include_router(auth_router)

# LOGIN REQUERIDO
from urllib.parse import quote
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool
from routers.auth import ACCESS_COOKIE, REFRESH_COOKIE, clear_session_cookies, set_session_cookies
from services.supabase_auth import AuthError, get_user, refresh_session

PUBLIC_PATHS = ("/login", "/signup", "/forgot-password", "/api/health")
PUBLIC_PREFIXES = ("/static/", "/auth/")

def is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)

@app.middleware("http")
async def require_login(request: Request, call_next):
    access_token = request.cookies.get(ACCESS_COOKIE)
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    user = await run_in_threadpool(get_user, access_token) if access_token else None

    # El token de acceso dura ~1 hora: si venció, se renueva con el de refresco
    new_session = None
    if user is None and refresh_token:
        try:
            new_session = await run_in_threadpool(refresh_session, refresh_token)
            user = new_session["user"]
            access_token = new_session["access_token"]
        except AuthError:
            pass

    request.state.user = user
    request.state.access_token = access_token if user else None

    if user is None and not is_public(request.url.path):
        if request.url.path.startswith("/api/"):
            response = JSONResponse({"detail": "Tu sesión expiró. Vuelve a iniciar sesión."}, status_code=401)
        else:
            target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
            response = RedirectResponse(f"/login?next={quote(target)}", status_code=303)
        if access_token or refresh_token:
            clear_session_cookies(response)
        return response

    response = await call_next(request)
    if new_session:
        set_session_cookies(response, new_session, request.url.scheme == "https")
    return response

def current_user_id(request: Request) -> str:
    return request.state.user["id"]

from services.sessions import (
    create_session,
    get_session_df,
    update_session_df,
    get_session_original_df,
    set_session_mapped_df,
    get_session_mapped_df,
    set_session_report_name,
    get_session_report_name,
    claim_once,
    set_session_clean_report,
    get_session_clean_report,
    get_session_filename
)
from services.user_stats import record_activity, get_stats, StatsUnavailable
from services.report_history import save_report, list_reports, get_report_pdf, HistoryUnavailable

@app.get("/api/health")
def health():
    return {"status": "ok"}

# UPLOAD 
@app.post("/api/upload")
async def upload_file(request: Request, background_tasks: BackgroundTasks, file: UploadFile = File(...)):

    if not file.filename.lower().endswith((".csv", ".xlsx")):
        raise HTTPException(400, "Este archivo no parece ser de ventas. Sube un Excel o CSV con tus ventas.")

    try:
        if file.filename.lower().endswith(".csv"):
            df = pd.read_csv(file.file)
        else:
            df = pd.read_excel(file.file)
    except Exception as e:
        raise HTTPException(400, f"Error leyendo archivo: {e}")

    if df.empty:
        raise HTTPException(400, "Archivo vacío")

    detected_columns = detect_sales_columns(df)
    missing_fields = validate_sales_file(df)
    

    # 🚫 No parece un archivo de ventas
    if len(detected_columns) == 0:
        raise HTTPException(
            status_code=400,
            detail="No se detectaron columnas de ventas. Asegúrate de subir un archivo con fechas, productos, cantidades y precios."
        )

    # 🚫 Demasiados campos obligatorios faltantes
    # if len(missing_fields) == len(SALES_SCHEMA["required"]):
    #     raise HTTPException(
    #         status_code=400,
    #         detail="Asegúrate de subir un archivo con fechas, productos, cantidades y precios."
    #     )

    session_id = create_session(df, SALES_SCHEMA, current_user_id(request), file.filename)
    # Se guarda después de responder para no hacer esperar al usuario
    background_tasks.add_task(record_activity, request.state.access_token, files=1)

    return {
        "status": "ok",
        "session_id": session_id,
        "filename": file.filename,
        "rows": len(df),
        "detected_columns": detected_columns,
        "required_fields": SALES_SCHEMA["required"],
        "all_columns": list(df.columns),
    }

@app.get("/")
def upload_page(request: Request):
    return templates.TemplateResponse(request, "index.html", {"request": request})

# PANEL DEL USUARIO
@app.get("/panel")
def panel_page(request: Request):
    user = request.state.user
    token = request.state.access_token
    try:
        stats = get_stats(token, user["id"])
    except StatsUnavailable:
        stats = None
    try:
        reports = list_reports(token)
    except HistoryUnavailable:
        reports = None

    return templates.TemplateResponse(
        request, "panel.html",
        {
            "request": request,
            "stats": stats,
            "reports": reports,
            "last_sign_in_at": user.get("last_sign_in_at"),
            "member_since": user.get("created_at"),
        }
    )

@app.get("/panel/reports/{report_id}/pdf")
def panel_report_pdf(request: Request, report_id: str):
    result = get_report_pdf(request.state.access_token, report_id)
    if result is None:
        raise HTTPException(404, "No encontramos el PDF de este informe.")

    filename, pdf = result
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# CLEAN
@app.get("/clean/{session_id}")
def clean_page(request: Request, session_id: str):
    return templates.TemplateResponse(
        request, "clean.html",
        {"request": request, "session_id": session_id}
    )

from models.payloads import ColumnMappingPayload
from services.mapping import apply_column_mapping

# MAPPING COLUMNS
@app.post("/api/map-columns/{session_id}")
def map_columns(request: Request, session_id: str, payload: ColumnMappingPayload):
    owner_id = current_user_id(request)
    df = get_session_original_df(session_id, owner_id)

    if df is None:
        raise HTTPException(404, "Sesión no encontrada")

    df = apply_column_mapping(df, payload.mapping)
    set_session_mapped_df(session_id, owner_id, df)
    set_session_report_name(session_id, owner_id, payload.report_name.strip())

    return {"status": "ok"}


from fastapi import Request, HTTPException
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

# MAP 
from services.auto_mapping import auto_map_columns

@app.get("/map/{session_id}")
def map_page(request: Request, session_id: str):
    df = get_session_original_df(session_id, current_user_id(request))

    if df is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    print(" File: ")
    print(df.head(3))

    auto_mapping = auto_map_columns(list(df.columns))

    return templates.TemplateResponse(
        request, "map.html",
        {
            "request": request,
            "session_id": session_id,
            "required": SALES_SCHEMA["required"],
            "optional": SALES_SCHEMA["optional"],
            "labels": SALES_SCHEMA["labels"],
            "columns": list(df.columns),
            "auto_mapping": auto_mapping
        }
    )

# Clean data
from services.cleaner import clean_sales_data
@app.post("/api/clean-data/{session_id}")
def clean_data(request: Request, session_id: str, background_tasks: BackgroundTasks):
    owner_id = current_user_id(request)
    df = get_session_mapped_df(session_id, owner_id)

    if df is None:
        raise HTTPException(404, "Sesión inválida")

    print("Columnas: ")
    print(df.columns)

    df_clean, report = clean_sales_data(df, SALES_SCHEMA)
    update_session_df(session_id, owner_id, df_clean)
    set_session_clean_report(session_id, owner_id, report)

    if claim_once(session_id, owner_id, "stats_recorded"):
        background_tasks.add_task(
            record_activity, request.state.access_token,
            processed=report["rows_initial"], fixed=report["rows_fixed"], removed=report["rows_removed"]
        )

    return {
        "status": "ok",
        "report": report,
        "rows": len(df_clean),
        "preview": df_clean.head(10).to_dict(orient="records")
    }

# Analyze data
from services.analyzer import analyze_sales_data
@app.post("/api/analyze/{session_id}")
def analyze_data(request: Request, session_id: str, background_tasks: BackgroundTasks):
    owner_id = current_user_id(request)
    df = get_session_df(session_id, owner_id)

    if df is None:
        raise HTTPException(404, "Sesión inválida")

    result = analyze_sales_data(df)

    # Primer análisis de este archivo: queda en el historial del panel con su PDF
    clean_report = get_session_clean_report(session_id, owner_id)
    if clean_report and claim_once(session_id, owner_id, "report_saved"):
        background_tasks.add_task(
            save_report, request.state.access_token, owner_id,
            get_session_filename(session_id, owner_id), get_session_report_name(session_id, owner_id),
            clean_report, result
        )

    return {
        "status": "ok",
        "analysis": result
    }

import io
from fastapi.responses import StreamingResponse
from datetime import date
from services.pdf_report import report_slug

# Export Data
@app.get("/export/{session_id}")
def export_data(request: Request, session_id: str):
    owner_id = current_user_id(request)
    df = get_session_df(session_id, owner_id)

    if df is None:
        raise HTTPException(404, "Sesión no encontrada")

    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)

    slug = report_slug(get_session_report_name(session_id, owner_id))
    filename = f"{slug}_data_{date.today()}.csv" if slug else f"datos_limpios_{date.today()}.csv"

    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


from services.pdf_report import build_sales_report_pdf

# Export PDF
@app.get("/export-pdf/{session_id}")
def export_pdf(request: Request, session_id: str):
    owner_id = current_user_id(request)
    df = get_session_df(session_id, owner_id)

    if df is None:
        raise HTTPException(404, "Sesión no encontrada")

    # La fecha solo es datetime después de limpiar los datos
    if "date" not in df.columns or not pd.api.types.is_datetime64_any_dtype(df["date"]):
        raise HTTPException(409, "Primero procesa el archivo para generar el PDF.")

    report_name = get_session_report_name(session_id, owner_id)
    pdf = build_sales_report_pdf(analyze_sales_data(df), report_name)

    slug = report_slug(report_name)
    filename = f"{slug}_report_{date.today()}.pdf" if slug else f"reporte_ventas_{date.today()}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


if __name__ == "__main__":
    import uvicorn
    print("Abre http://127.0.0.1:8000 en tu navegador")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
