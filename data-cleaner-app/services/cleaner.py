import re
import pandas as pd
from fastapi import HTTPException

from fastapi import HTTPException
import pandas as pd

def clean_sales_data(df, schema):
    report = {}

    # 1️⃣ Eliminar filas completamente vacías
    before = len(df)
    df = df.dropna(how="all")
    report["rows_removed_nulls"] = before - len(df)

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="El archivo está vacío después de eliminar filas nulas."
        )

    # 2️⃣ LIMPIEZA NUMÉRICA (quantity y price si existen)
    numeric_columns = ["quantity", "price"]

    for col in numeric_columns:
        if col in df.columns:
            before = len(df)

            df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df[df[col].notna()]

            removed = before - len(df)
            report[f"rows_removed_invalid_{col}"] = removed

    if df.empty:
        raise HTTPException(
            status_code=422,
            detail="Todas las filas fueron eliminadas por valores no numéricos en columnas críticas."
        )

    # 3️⃣ Conversión según schema dinámico
    for col, dtype in schema["types"].items():
        if col not in df.columns:
            continue

        if dtype == "int":
            df[col] = pd.to_numeric(df[col], errors="coerce")
        elif dtype == "float":
            df[col] = pd.to_numeric(df[col], errors="coerce")
        elif dtype == "datetime":
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # 4️⃣ Eliminar nulos generados por conversiones
    before = len(df)
    df = df.dropna()
    report["rows_removed_after_types"] = before - len(df)

    if df.empty:
        raise HTTPException(
            status_code=422,
            detail="No quedaron filas válidas después de aplicar el esquema de tipos."
        )

    # 5️⃣ Eliminar duplicados
    before = len(df)
    df = df.drop_duplicates()
    report["rows_removed_duplicates"] = before - len(df)

    report["rows_final"] = len(df)

    print("📊 Reporte Final:", report)

    return df, report

# def clean_sales_data(df, schema):
#     report = {}

#     # eliminar filas completamente vacías
#     before = len(df)
#     df = df.dropna(how="all")
#     report["rows_removed_nulls"] = before - len(df)

#     # 🔹 VALIDACIÓN ESPECÍFICA PARA quantity
#     if "quantity" in df.columns:
#         invalid_mask = df["quantity"].astype(str).str.contains(r"[a-zA-Z]", regex=True)

#         if invalid_mask.any():
#             invalid_values = df.loc[invalid_mask, "quantity"].unique()

#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Se detectaron valores inválidos en la columna quantity."
#             )
        
#     if "price" in df.columns:
#         invalid_mask = df["price"].astype(str).str.contains(r"[a-zA-Z]", regex=True)

#         if invalid_mask.any():
#             invalid_values = df.loc[invalid_mask, "price"].unique()

#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Se detectaron valores inválidos en en la columna price."
#             )

#     # 🔹 convertir tipos
#     for col, dtype in schema["types"].items():
#         if col not in df.columns:
#             continue

#         if dtype == "int":
#             df[col] = pd.to_numeric(df[col], errors="raise")
#         elif dtype == "float":
#             df[col] = pd.to_numeric(df[col], errors="raise")
#         elif dtype == "datetime":
#             df[col] = pd.to_datetime(df[col], errors="raise")

#     # eliminar nulos generados por conversiones
#     before = len(df)
#     df = df.dropna()
    
#     report["rows_removed_after_types"] = before - len(df)

#     # eliminar duplicados
#     before = len(df)
#     df = df.drop_duplicates()
#     report["rows_removed_duplicates"] = before - len(df)

#     report["rows_final"] = len(df)

#     print(" Reporte FInal: ")
#     print(df)
#     print(" ")

#     return df, report
