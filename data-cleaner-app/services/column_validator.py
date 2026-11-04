import re
import pandas as pd
from fastapi import HTTPException
from services.schema import REQUIRED_FIELDS
from services.schema import SALES_SCHEMA
from services.cleaner import parse_number

def is_numeric_column(series) -> bool:
    return pd.to_numeric(series.map(parse_number), errors="coerce").notna().all()

def normalize_column(col: str) -> str:
    """
    Normaliza nombres de columnas:
    - minúsculas
    - sin espacios
    - sin símbolos
    """
    col = col.strip().lower()
    col = re.sub(r"[^\w]", "_", col)
    return col

def detect_sales_columns(df):
    normalized_cols = {
        normalize_column(col): col for col in df.columns
    }

    detected = {}

    for canonical, aliases in SALES_SCHEMA["required"].items():
        for alias in aliases:
            alias_norm = normalize_column(alias)
            for col_norm, original in normalized_cols.items():
                if alias_norm in col_norm:
                    detected[canonical] = original
                    break
            if canonical in detected:
                break

    return detected

def validate_sales_file(df):

    if len(df.columns) < 4:
        raise HTTPException(
            400,
            "Asegúrate de subir un archivo con fechas, productos, cantidades y precios."
        )

    detected = detect_sales_columns(df)

    ratio = len(detected) / len(SALES_SCHEMA["required"])

    MIN_MATCH_RATIO = 0.7
    if ratio < MIN_MATCH_RATIO:
        raise HTTPException(
            400,
            "Asegúrate de subir un archivo con fechas, productos, cantidades y precios."
        )

    # 🔹 NUEVO: validar tipos reales
    validate_column_types(df, detected)

    return detected

def validate_column_types(df, detected):
    errors = []

    for canonical, original_col in detected.items():
        series = df[original_col].dropna()

        if canonical == "date":
            try:
                pd.to_datetime(series, errors="raise")
            except:
                errors.append("La columna de fecha no contiene fechas válidas.")

        elif canonical == "quantity":
            if not is_numeric_column(series):
                errors.append("La columna de cantidad debe ser numérica.")

        elif canonical == "price":
            if not is_numeric_column(series):
                errors.append("La columna de precio debe ser numérica.")

        elif canonical == "product":
            if pd.api.types.is_datetime64_any_dtype(series):
                errors.append("La columna de producto no puede ser tipo fecha.")

    if errors:
        raise HTTPException(400, " ".join(errors))
