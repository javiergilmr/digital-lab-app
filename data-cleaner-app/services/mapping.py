from fastapi import HTTPException
from services.schema import ALL_FIELDS, SALES_SCHEMA

def apply_column_mapping(df, mapping):
    """mapping = {columna_original: campo_canónico}. Las columnas no asignadas se conservan."""
    # Solo se aceptan campos conocidos, y cada campo una sola vez
    mapping = {col: field for col, field in mapping.items() if field in ALL_FIELDS and col in df.columns}
    if len(set(mapping.values())) != len(mapping):
        raise HTTPException(400, "Cada campo debe asignarse a una sola columna.")

    missing = [SALES_SCHEMA["labels"][f] for f in SALES_SCHEMA["required"] if f not in mapping.values()]
    if missing:
        raise HTTPException(400, f"Faltan columnas obligatorias: {', '.join(missing)}.")

    # Una columna no asignada que ya se llame como un campo (ej. "price") se renombra
    # para no quedar duplicada con la que sí se eligió
    targets = set(mapping.values())
    renames = {}
    for col in df.columns:
        if col in mapping:
            renames[col] = mapping[col]
        elif col in targets:
            renames[col] = f"{col}_original"

    return df.rename(columns=renames)
