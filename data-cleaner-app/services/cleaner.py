import re
import unicodedata

import pandas as pd
from fastapi import HTTPException

from services.schema import SALES_SCHEMA

REQUIRED = list(SALES_SCHEMA["required"])
NUMERIC_FIELDS = ["quantity", "price", "net_sales", "unit_cost", "total_cost", "profit"]
LABELS = SALES_SCHEMA["labels"]

# Diferencia en centavos que se acepta por redondeo antes de recalcular un total
TOLERANCE = 0.02

# Para corregir un valor por mayoría (ej. la categoría de un producto) hace falta
# que al menos 2 filas coincidan y que sean más de la mitad
MIN_MAJORITY_ROWS = 2


# =========================
# CONVERSIONES
# =========================

def parse_number(value):
    """Convierte '19,99', '1.500,75' o '$1,500.75' a número. Devuelve el texto si no es un número."""
    if not isinstance(value, str):
        return value

    text = re.sub(r"[\s$€£]", "", value)
    last_comma, last_dot = text.rfind(","), text.rfind(".")

    if last_comma >= 0 and last_dot >= 0:
        # Con ambos separadores, el último es el decimal
        thousands, decimal = (".", ",") if last_comma > last_dot else (",", ".")
        text = text.replace(thousands, "").replace(decimal, ".")
    elif text.count(",") > 1 or text.count(".") > 1:
        # Un separador repetido solo puede ser de miles: 1.500.000
        text = text.replace(",", "").replace(".", "")
    elif last_comma >= 0:
        # Una sola coma con 3 cifras detrás se toma como miles: 1,500
        digits_after = len(text) - last_comma - 1
        text = text.replace(",", "" if digits_after == 3 else ".")

    try:
        return float(text)
    except ValueError:
        return value

def parse_numbers(series):
    return pd.to_numeric(series.map(parse_number), errors="coerce")

def parse_dates(series):
    """Fechas inválidas (ej. 2026-13-05) quedan vacías en lugar de romper toda la columna."""
    parsed = pd.to_datetime(series, errors="coerce")
    if len(parsed) and parsed.notna().mean() < 0.8:
        parsed = pd.to_datetime(series, errors="coerce", format="mixed")
    return parsed

def text_key(value):
    """'Tarjeta Débito ' y 'tarjeta debito' comparten la misma clave."""
    text = unicodedata.normalize("NFKD", str(value).lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.split())


# =========================
# REPORTE
# =========================

ROWS = ("fila", "filas")
VALUES = ("valor", "valores")

class CleaningReport:
    def __init__(self, rows_initial):
        self.rows_initial = rows_initial
        self.actions = []
        # Índices de las filas tocadas: una fila con varias correcciones cuenta una sola vez
        self.fixed_rows = set()
        self.removed_rows = set()

    def add(self, mask, message, removed=False, values=None):
        """mask = filas afectadas (Serie booleana); values = celdas cambiadas, si se cuenta por valor.
        "Acción: N filas" concuerda en singular y plural sin conjugar verbos."""
        (self.removed_rows if removed else self.fixed_rows).update(mask[mask].index)
        count, unit = (int(mask.sum()), ROWS) if values is None else (int(values), VALUES)
        if count:
            self.actions.append({
                "count": count,
                "message": f"{message}: {count} {unit[count != 1]}",
                "kind": "removed" if removed else "fixed",
            })

    def to_dict(self, rows_final):
        return {
            "rows_initial": int(self.rows_initial),
            "rows_final": int(rows_final),
            "rows_removed": int(self.rows_initial - rows_final),
            "rows_fixed": len(self.fixed_rows - self.removed_rows),
            "actions": self.actions,
        }


# =========================
# PASOS
# =========================

def _is_text(series):
    return pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series)

def _label(col):
    return LABELS.get(col, col)

def _trim_text(df, report):
    rows = pd.Series(False, index=df.index)
    changed = 0
    for col in [c for c in df.columns if _is_text(df[c])]:
        original = df[col]
        cleaned = original.map(lambda v: " ".join(v.split()) or None if isinstance(v, str) else v)
        mask = original.notna() & (cleaned.astype(object) != original.astype(object))
        changed += int(mask.sum())
        rows |= mask
        df[col] = cleaned
    report.add(rows, "Espacios de sobra quitados", values=changed)
    return df

def _unify_spellings(df, report):
    """Unifica variantes que solo difieren en mayúsculas, tildes o espacios."""
    for col in [c for c in df.columns if _is_text(df[c])]:
        values = df[col].dropna()
        # Columnas casi únicas (ids de transacción o cliente) no tienen variantes que unificar
        if values.empty or values.nunique() > 0.5 * len(values):
            continue

        keys = values.map(text_key)
        preferred = values.groupby(keys).agg(lambda s: s.value_counts().idxmax())
        unified = df[col].map(lambda v: preferred.get(text_key(v), v) if isinstance(v, str) else v)

        mask = df[col].notna() & (unified.astype(object) != df[col].astype(object))
        df[col] = unified
        report.add(mask, f"Escritura unificada en «{_label(col)}» (mayúsculas, tildes o espacios)", values=mask.sum())
    return df

def _fix_by_majority(df, key_col, value_col):
    """Cada key (ej. código de producto) toma el valor más frecuente de value_col si hay mayoría clara."""
    fixed = pd.Series(False, index=df.index)
    pairs = df[[key_col, value_col]].dropna()
    if pairs.empty:
        return df, fixed

    counts = pairs.groupby([key_col, value_col]).size()
    for key, group in counts.groupby(level=0):
        top = group.max()
        if top < MIN_MAJORITY_ROWS or top / group.sum() <= 0.5:
            continue
        top_value = group.idxmax()[1]
        values = df[value_col].astype(object)
        mask = (df[key_col].astype(object) == key) & (values.isna() | (values != top_value))
        fixed |= mask
        df.loc[mask, value_col] = top_value
    return df, fixed

def _drop(df, mask, report, message):
    report.add(mask, message, removed=True)
    return df[~mask]

def _fix_prices(df, report):
    """Precio negativo o vacío: se usa el precio habitual (mediana) del mismo producto."""
    bad = df["price"].isna() | (df["price"] < 0)
    if not bad.any():
        return df

    usual = df.loc[~bad].groupby("product")["price"].median()
    replacement = df.loc[bad, "product"].map(usual)
    fixable = replacement.notna()

    df.loc[replacement[fixable].index, "price"] = replacement[fixable]
    report.add(fixable, "Precio negativo o vacío reemplazado por el precio habitual del producto")

    still_bad = df["price"].isna() | (df["price"] < 0)
    return _drop(df, still_bad, report, "Eliminadas por precio inválido sin forma de deducirlo")

def _fix_quantities(df, report):
    """Cantidad 0, vacía o con signo contrario a la venta: se deduce de costo total ÷ costo unitario."""
    qty = df["quantity"]
    bad = qty.isna() | (qty == 0)
    if "net_sales" in df.columns:
        bad |= (qty < 0) & (df["net_sales"] > 0)
    if not bad.any():
        return df

    if {"total_cost", "unit_cost"} <= set(df.columns):
        derived = (df["total_cost"] / df["unit_cost"]).where(df["unit_cost"] > 0)
        # Solo se acepta si da un número entero (o casi): así no se inventan cantidades
        exact = (derived - derived.round()).abs() < 0.01
        fixable = bad & derived.notna() & exact & (derived.round() > 0)
        df.loc[fixable, "quantity"] = derived[fixable].round()
        report.add(fixable, "Cantidad 0 o inválida corregida con costo total ÷ costo unitario")
        bad &= ~fixable

    return _drop(df, bad, report, "Eliminadas por cantidad 0 o inválida sin forma de deducirla")

def _fix_totals(df, report):
    """Costo total = cantidad × costo unitario; utilidad = venta neta − costo total."""
    cols = set(df.columns)

    if {"total_cost", "unit_cost"} <= cols:
        expected = (df["quantity"] * df["unit_cost"]).round(2)
        wrong = expected.notna() & (df["total_cost"].isna() | ((df["total_cost"] - expected).abs() > TOLERANCE))
        df.loc[wrong, "total_cost"] = expected[wrong]
        report.add(wrong, "Costo total recalculado (cantidad × costo unitario)")

    if "net_sales" in cols:
        empty = df["net_sales"].isna()
        df.loc[empty, "net_sales"] = (df["quantity"] * df["price"]).round(2)[empty]
        report.add(empty, "Venta neta vacía estimada como cantidad × precio")

    if {"profit", "net_sales", "total_cost"} <= cols:
        expected = (df["net_sales"] - df["total_cost"]).round(2)
        wrong = expected.notna() & (df["profit"].isna() | ((df["profit"] - expected).abs() > TOLERANCE))
        df.loc[wrong, "profit"] = expected[wrong]
        report.add(wrong, "Utilidad recalculada (venta neta − costo total)")

    return df


# =========================
# LIMPIEZA
# =========================

def clean_sales_data(df, schema):
    # Índice limpio para poder contar cada fila corregida una sola vez
    df = df.reset_index(drop=True)
    report = CleaningReport(len(df))

    # 1️⃣ Filas completamente vacías
    df = _drop(df, df.isna().all(axis=1), report, "Filas vacías eliminadas")

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="El archivo está vacío después de eliminar filas nulas."
        )

    # 2️⃣ Textos: espacios de sobra y variantes de escritura
    df = _trim_text(df, report)
    df = _unify_spellings(df, report)

    # 3️⃣ Fechas imposibles (ej. mes 13): no se pueden deducir, se eliminan
    original_dates = df["date"]
    df["date"] = parse_dates(df["date"])
    df = _drop(df, df["date"].isna() & original_dates.notna(), report,
               "Eliminadas por fecha inválida")

    # 4️⃣ Números (acepta '19,99', '$1,500.75'...)
    for col in [c for c in NUMERIC_FIELDS if c in df.columns]:
        original = df[col]
        df[col] = parse_numbers(original)
        if col not in REQUIRED:
            invalid = df[col].isna() & original.notna()
            report.add(invalid, f"Valores no numéricos en «{_label(col)}» dejados en blanco", values=invalid.sum())

    # 5️⃣ Coherencia entre columnas: el valor más frecuente para el mismo producto o tienda
    for key_col, value_col, message in [
        ("product", "category", "Categoría corregida según el producto"),
        ("store_id", "store_city", "Ciudad corregida según la tienda"),
    ]:
        if {key_col, value_col} <= set(df.columns):
            df, fixed = _fix_by_majority(df, key_col, value_col)
            report.add(fixed, message)

    # 6️⃣ Precio y cantidad
    df = _fix_prices(df, report)
    df = _fix_quantities(df, report)

    # 7️⃣ Totales que deben cuadrar
    df = _fix_totals(df, report)

    # 8️⃣ Datos obligatorios vacíos
    df = _drop(df, df[REQUIRED].isna().any(axis=1), report,
               "Eliminadas por no tener fecha, producto, cantidad o precio")

    # 9️⃣ Duplicados exactos
    df = _drop(df, df.duplicated(), report, "Filas duplicadas eliminadas")

    if df.empty:
        raise HTTPException(
            status_code=422,
            detail="No quedaron filas válidas después de limpiar los datos."
        )

    result = report.to_dict(len(df))
    print("📊 Reporte Final:", result)

    return df.reset_index(drop=True), result
