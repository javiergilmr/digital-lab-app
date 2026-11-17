import logging
import os
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
import pandas as pd
from services.column_validator import detect_sales_columns, validate_sales_file, validate_column_types
from services.schema import SALES_SCHEMA, ALL_FIELDS
from routers.api import router as api_router

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

# Nivel con la variable LOG_LEVEL (DEBUG muestra el detalle de cada limpieza)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("data_cleaner")

app = FastAPI()
from services.templating import templates
app.include_router(api_router, prefix="/api")

from routers.pages import router as pages_router
from routers.auth import router as auth_router

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(pages_router)
app.include_router(auth_router)

# LOGIN OPCIONAL
# Sin cuenta se usa todo el flujo (subir → mapear → procesar → informe → descargas) como invitado.
# Con cuenta, además, se guardan los stats y el historial del panel.
import uuid
from urllib.parse import quote
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool
from routers.auth import ACCESS_COOKIE, REFRESH_COOKIE, clear_session_cookies, set_session_cookies
from services.supabase_auth import AuthError, get_user, refresh_session
from services.sessions import adopt_sessions, SESSION_TTL

PUBLIC_PATHS = ("/login", "/signup", "/forgot-password", "/sobre-nosotros", "/api/health")
PUBLIC_PREFIXES = ("/static/", "/auth/")
# Lo que un invitado puede usar; el panel y la cuenta piden iniciar sesión
GUEST_PATHS = ("/", "/api/upload", "/api/demo")
GUEST_PREFIXES = ("/map/", "/clean/", "/export/", "/export-pdf/",
                  "/api/map-columns/", "/api/clean-data/", "/api/analyze/")
GUEST_COOKIE = "guest_id"

def is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)

def is_guest_allowed(path: str) -> bool:
    return path in GUEST_PATHS or path.startswith(GUEST_PREFIXES)

def valid_guest_id(value) -> bool:
    try:
        return uuid.UUID(hex=value).hex == value
    except (TypeError, ValueError):
        return False

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

    # Invitado: un id al azar en una cookie identifica sus archivos (las sesiones en memoria)
    guest_id = request.cookies.get(GUEST_COOKIE)
    guest_id = guest_id if valid_guest_id(guest_id) else None
    new_guest = False
    if user is None and guest_id is None and is_guest_allowed(request.url.path):
        guest_id, new_guest = uuid.uuid4().hex, True
    request.state.guest_id = guest_id

    # Al iniciar sesión, los archivos que subió como invitado pasan a su cuenta
    adopted = False
    if user and guest_id:
        adopt_sessions(f"guest:{guest_id}", user["id"])
        adopted = True

    if user is None and not is_public(request.url.path) and not is_guest_allowed(request.url.path):
        if request.url.path.startswith("/api/"):
            response = JSONResponse({"detail": "Tu sesión expiró. Vuelve a iniciar sesión."}, status_code=401)
        else:
            target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
            response = RedirectResponse(f"/login?next={quote(target)}", status_code=303)
        if access_token or refresh_token:
            clear_session_cookies(response)
        return response

    response = await call_next(request)
    secure = request.url.scheme == "https"
    if new_session:
        set_session_cookies(response, new_session, secure)
    elif user is None and (access_token or refresh_token):
        # Tokens vencidos o inválidos en una página de invitado: se limpian
        clear_session_cookies(response)
    if new_guest:
        response.set_cookie(GUEST_COOKIE, guest_id, max_age=SESSION_TTL,
                            httponly=True, samesite="lax", secure=secure, path="/")
    if adopted:
        response.delete_cookie(GUEST_COOKIE, path="/")
    return response

def current_user_id(request: Request) -> str:
    """Dueño de los archivos subidos: el usuario con sesión o el invitado de esta cookie."""
    if request.state.user:
        return request.state.user["id"]
    return f"guest:{request.state.guest_id}"

def is_logged_in(request: Request) -> bool:
    return request.state.user is not None

from services.sessions import (
    create_session,
    get_session_df,
    update_session_df,
    get_session_original_df,
    set_session_mapped_df,
    set_session_mapping,
    get_session_mapping,
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
from services.account import AccountError, access_methods, has_password, change_password, delete_account
from services.monthly_quota import QuotaExceeded, claim_file, get_usage

def monthly_usage(request: Request):
    return get_usage(request.state.user, request.state.access_token, request.state.guest_id)

@app.get("/api/health")
def health():
    return {"status": "ok"}

# UPLOAD 
# Protege la memoria del servidor: un archivo más grande no cabe en una instancia pequeña
MAX_UPLOAD_MB = 10

@app.post("/api/upload")
async def upload_file(request: Request, background_tasks: BackgroundTasks, file: UploadFile = File(...)):

    if not file.filename.lower().endswith((".csv", ".xlsx")):
        raise HTTPException(400, "Este archivo no parece ser de ventas. Sube un Excel o CSV con tus ventas.")

    if file.size is not None and file.size > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"El archivo pesa más de {MAX_UPLOAD_MB} MB. Sube uno más liviano.")

    try:
        if file.filename.lower().endswith(".csv"):
            df = pd.read_csv(file.file)
        else:
            df = pd.read_excel(file.file)
    except Exception as e:
        raise HTTPException(400, f"Error leyendo archivo: {e}")

    return start_session(request, background_tasks, df, file.filename, count_quota=True)

# Datos de ejemplo: un año de ventas de 4 tiendas con errores típicos para que la limpieza tenga qué mostrar.
# No cuentan para el límite mensual: son para conocer la app
DEMO_FILE = Path(__file__).resolve().parent / "static" / "demo_ventas.csv"
DEMO_REPORT_NAME = "Tiendas Demo"

@app.post("/api/demo")
def demo_file(request: Request, background_tasks: BackgroundTasks):
    df = pd.read_csv(DEMO_FILE)
    result = start_session(request, background_tasks, df, DEMO_FILE.name)
    set_session_report_name(result["session_id"], current_user_id(request), DEMO_REPORT_NAME)
    return result

def start_session(request: Request, background_tasks: BackgroundTasks, df, filename, count_quota=False):
    """Valida que parezca un archivo de ventas, lo cuenta en el límite del mes y crea la sesión del archivo."""
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

    # Se cuenta después de validar: un archivo rechazado no gasta cupo
    if count_quota:
        try:
            claim_file(request.state.user, request.state.access_token, request.state.guest_id)
        except QuotaExceeded as e:
            raise HTTPException(429, e.message)

    session_id = create_session(df, SALES_SCHEMA, current_user_id(request), filename)
    # Solo con cuenta hay stats; se guardan después de responder para no hacer esperar al usuario
    if is_logged_in(request):
        background_tasks.add_task(record_activity, request.state.access_token, files=1)

    return {
        "status": "ok",
        "session_id": session_id,
        "filename": filename,
        "rows": len(df),
        "detected_columns": detected_columns,
        "required_fields": SALES_SCHEMA["required"],
        "all_columns": list(df.columns),
    }

@app.get("/")
def upload_page(request: Request):
    return templates.TemplateResponse(request, "index.html", {"request": request, "usage": monthly_usage(request)})

# PANEL DEL USUARIO
@app.get("/panel")
def panel_page(request: Request, ok: str = ""):
    notice = "Tu contraseña se cambió correctamente." if ok == "password" else None
    return render_panel(request, password_notice=notice)

def render_panel(request: Request, status_code=200, **messages):
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
            "usage": monthly_usage(request),
            "last_sign_in_at": user.get("last_sign_in_at"),
            "member_since": user.get("created_at"),
            "access_methods": access_methods(user),
            "has_password": has_password(user),
            **messages,
        },
        status_code=status_code
    )

@app.post("/panel/password")
def panel_change_password(
    request: Request, current: str = Form(...), password: str = Form(...), confirm: str = Form(...)
):
    if not has_password(request.state.user):
        raise HTTPException(400, "Tu cuenta entra con Google y no tiene contraseña.")
    try:
        change_password(request.state.user, current, password, confirm)
    except AccountError as e:
        return render_panel(request, status_code=400, password_error=e.message)
    return RedirectResponse("/panel?ok=password#cuenta", status_code=303)

@app.post("/panel/delete-account")
def panel_delete_account(request: Request, confirm_email: str = Form(...)):
    try:
        delete_account(request.state.user, request.state.access_token, confirm_email)
    except AccountError as e:
        return render_panel(request, status_code=400, delete_error=e.message)

    response = RedirectResponse("/login?deleted=1", status_code=303)
    clear_session_cookies(response)
    return response

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
    # Sesión vencida (2 h sin uso), de otro usuario o inexistente: se vuelve a la carga con un aviso
    if get_session_original_df(session_id, current_user_id(request)) is None:
        return RedirectResponse("/?expired=1", status_code=303)
    return templates.TemplateResponse(
        request, "clean.html",
        {
            "request": request,
            "session_id": session_id,
            "report_name": get_session_report_name(session_id, current_user_id(request))
        }
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

    mapped = apply_column_mapping(df, payload.mapping)
    set_session_mapped_df(session_id, owner_id, mapped)
    set_session_mapping(session_id, owner_id, {
        field: col for col, field in payload.mapping.items() if col in df.columns and field in ALL_FIELDS
    })
    set_session_report_name(session_id, owner_id, payload.report_name.strip())

    return {"status": "ok"}


from fastapi import Request, HTTPException
# MAP 
from services.auto_mapping import auto_map_columns

@app.get("/map/{session_id}")
def map_page(request: Request, session_id: str):
    owner_id = current_user_id(request)
    df = get_session_original_df(session_id, owner_id)

    if df is None:
        return RedirectResponse("/?expired=1", status_code=303)

    auto_mapping = auto_map_columns(list(df.columns))
    # Si ya se mapeó (ej. al volver desde Procesar), se muestra lo elegido y no lo automático
    saved_mapping = get_session_mapping(session_id, owner_id)

    return templates.TemplateResponse(
        request, "map.html",
        {
            "request": request,
            "session_id": session_id,
            "required": SALES_SCHEMA["required"],
            "optional": SALES_SCHEMA["optional"],
            "labels": SALES_SCHEMA["labels"],
            "columns": list(df.columns),
            "auto_mapping": auto_mapping,
            "selected": saved_mapping if saved_mapping is not None else auto_mapping,
            "report_name": get_session_report_name(session_id, owner_id)
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

    df_clean, report = clean_sales_data(df, SALES_SCHEMA)
    update_session_df(session_id, owner_id, df_clean)
    set_session_clean_report(session_id, owner_id, report)

    if is_logged_in(request) and claim_once(session_id, owner_id, "stats_recorded"):
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
    if clean_report and is_logged_in(request) and claim_once(session_id, owner_id, "report_saved"):
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
    log.info("Abre http://127.0.0.1:8000 en tu navegador")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
