import unicodedata
from services.schema import ALL_FIELDS

def normalize(text: str) -> str:
    text = str(text).lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.replace(" ", "").replace("_", "").replace("-", "").replace(".", "")

def _is_id(name: str) -> bool:
    return name.endswith("id") or name.startswith("id")

def _score(norm_col: str, norm_names) -> int:
    """Qué tan bien coincide una columna con un campo: 100 exacto, menos si solo lo contiene."""
    best = 0
    for name in norm_names:
        if norm_col == name:
            return 100
        # "product" no debe tomar "product_id": un identificador solo va a un campo de identificador
        if _is_id(norm_col) and not _is_id(name):
            continue
        if len(name) >= 3 and name in norm_col:
            best = max(best, 60 - (len(norm_col) - len(name)))
    return best if best >= 20 else 0

def match_columns(fields: dict, df_columns) -> dict:
    """Asigna a cada campo la columna que mejor coincide; cada columna se usa una sola vez."""
    candidates = []
    for field, aliases in fields.items():
        norm_names = [normalize(field)] + [normalize(a) for a in aliases]
        for col in df_columns:
            score = _score(normalize(col), norm_names)
            if score:
                candidates.append((score, field, col))

    mapping, used = {}, set()
    for score, field, col in sorted(candidates, key=lambda c: -c[0]):
        if field in mapping or col in used:
            continue
        mapping[field] = col
        used.add(col)
    return mapping

def auto_map_columns(df_columns, fields=None):
    return match_columns(fields or ALL_FIELDS, df_columns)
