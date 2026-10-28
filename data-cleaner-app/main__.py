# from fastapi import FastAPI
# from fastapi.staticfiles import StaticFiles
# from fastapi.templating import Jinja2Templates

# from pydantic import BaseModel
# from typing import Dict

# from app.routers.api import router as api_router
# from app.routers.pages import router as pages_router

# app = FastAPI(title="Data Cleaner API")
# app.mount("/static", StaticFiles(directory="app/static"), name="static")

# templates = Jinja2Templates(directory="templates")

# app.include_router(api_router, prefix="/api")
# app.include_router(pages_router)

# from fastapi import APIRouter, UploadFile, File, HTTPException
# from fastapi.responses import StreamingResponse
# import pandas as pd
# import io
# from datetime import date

# from app.services.sessions import (
#     create_session,
#     get_session,
#     update_session
# )
# from app.services.column_validator import detect_columns, validate_required_fields
# from app.services.mapper import apply_column_mapping
# from app.services.data_cleaner import clean_sales_data
# from app.services.schema import SALES_SCHEMA, REQUIRED_FIELDS
# from app.services.mapper import apply_column_mapping
# from app.services.schema import REQUIRED_FIELDS

# from fastapi import FastAPI
# from app.routers.api import router as api_router
# app = FastAPI()

# app.include_router(api_router, prefix="/api")
# router = APIRouter()

# app = FastAPI()
# templates = Jinja2Templates(directory="templates")

# class ColumnMappingPayload(BaseModel):
#     mapping: Dict[str, str]

# SESSIONS = {}
# SALES_SCHEMA = {}

# def get_session_df(session_id: str):
#     session = SESSIONS.get(session_id)
#     return session["df"] if session else None

# def get_session_schema(session_id: str):
#     session = SESSIONS.get(session_id)
#     return session["schema"] if session else None

# def update_session_df(session_id: str, df):
#     if session_id in SESSIONS:
#         SESSIONS[session_id]["df"] = df

# from fastapi import APIRouter
# router = APIRouter()

# @router.get("/health", tags=["Health"])
# def health():
#     return {"status": "ok"}

# @router.post("/upload")
# async def upload_file(file: UploadFile = File(...)):

#     if not file.filename.endswith((".csv", ".xlsx")):
#         raise HTTPException(400, "Formato no soportado")

#     try:
#         if file.filename.endswith(".csv"):
#             df = pd.read_csv(file.file)
#         else:
#             df = pd.read_excel(file.file)
#     except Exception as e:
#         raise HTTPException(400, f"Error leyendo archivo: {e}")

#     if df.empty:
#         raise HTTPException(400, "Archivo vacío")

#     detected_columns = detect_columns(df)
#     missing_fields = validate_required_fields(detected_columns)

#     session_id = create_session(df, SALES_SCHEMA)

#     return {
#         "status": "mapping_required" if missing_fields else "ok",
#         "session_id": session_id,
#         "missing_fields": missing_fields,
#         "detected_columns": detected_columns,
#         "all_columns": list(df.columns),
#         "preview": df.head(20).to_dict("records")
#     }

# @router.post("/map-columns/{session_id}")
# def map_columns(session_id: str, payload: dict):

#     df = get_session_df(session_id)
#     if df is None:
#         raise HTTPException(404, "Sesión no encontrada")

#     df = apply_column_mapping(df, payload["mapping"])
#     update_session_df(session_id, df)

#     return {"status": "ok", "columns": list(df.columns)}

# @router.post("/clean/{session_id}")
# def clean_data(session_id: str):

#     df = get_session_df(session_id)
#     schema = get_session_schema(session_id)

#     if df is None:
#         raise HTTPException(404, "Sesión inválida")

#     df_clean, report = clean_sales_data(df, schema)
#     update_session_df(session_id, df_clean)

#     return {
#         "status": "ok",
#         "rows_finales": len(df_clean),
#         "reporte": report,
#         "preview": df_clean.head(20).to_dict("records")
#     }

# @router.get("/export/{session_id}")
# def export_data(session_id: str):

#     df = get_session_df(session_id)
#     if df is None:
#         raise HTTPException(404, "Sesión no encontrada")

#     buffer = io.StringIO()
#     df.to_csv(buffer, index=False)
#     buffer.seek(0)

#     filename = f"datos_limpios_{date.today()}.csv"

#     return StreamingResponse(
#         buffer,
#         media_type="text/csv",
#         headers={"Content-Disposition": f"attachment; filename={filename}"}
#     )

# from fastapi import APIRouter, Request
# from fastapi.templating import Jinja2Templates

# router = APIRouter()
# templates = Jinja2Templates(directory="templates")

# @router.get("/")
# def upload_page(request: Request):
#     return templates.TemplateResponse("upload.html", {"request": request})

# @router.get("/map/{session_id}")
# def map_page(request: Request, session_id: str):
#     return templates.TemplateResponse(
#         "map.html",
#         {"request": request, "session_id": session_id}
#     )

# @router.get("/clean/{session_id}")
# def clean_page(request: Request, session_id: str):
#     return templates.TemplateResponse(
#         "clean.html",
#         {"request": request, "session_id": session_id}
#     )

