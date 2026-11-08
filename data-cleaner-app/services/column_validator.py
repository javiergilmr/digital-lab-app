import pandas as pd
from fastapi import HTTPException
from services.schema import SALES_SCHEMA
from services.cleaner import parse_dates, parse_numbers
from services.auto_mapping import match_columns

# Una columna se acepta si al menos este porcentaje de sus valores es válido;
# las filas sueltas con errores las corrige o elimina la limpieza y quedan en el reporte
MIN_VALID_SHARE = 0.8

def valid_share(parsed) -> float:
    return parsed.notna().mean() if len(parsed) else 1.0

def detect_sales_columns(df):
    return match_columns(SALES_SCHEMA["required"], df.columns)

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

    validate_column_types(df, detected)

    return detected

def validate_column_types(df, detected):
    errors = []

    for canonical, original_col in detected.items():
        series = df[original_col].dropna()

        if canonical == "date":
            if valid_share(parse_dates(series)) < MIN_VALID_SHARE:
                errors.append("La columna de fecha no contiene fechas válidas.")

        elif canonical == "quantity":
            if valid_share(parse_numbers(series)) < MIN_VALID_SHARE:
                errors.append("La columna de cantidad debe ser numérica.")

        elif canonical == "price":
            if valid_share(parse_numbers(series)) < MIN_VALID_SHARE:
                errors.append("La columna de precio debe ser numérica.")

        elif canonical == "product":
            if pd.api.types.is_datetime64_any_dtype(series):
                errors.append("La columna de producto no puede ser tipo fecha.")

    if errors:
        raise HTTPException(400, " ".join(errors))
