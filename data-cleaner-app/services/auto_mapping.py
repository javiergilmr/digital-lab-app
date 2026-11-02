import unicodedata
from services.schema import ALIASES

def normalize(text: str) -> str:
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.replace(" ", "").replace("_", "").replace("-", "")

def auto_map_columns(required_fields, df_columns):
    mapping = {}
    norm_columns = {normalize(col): col for col in df_columns}

    for field in required_fields:
        norm_field = normalize(field)

        # 1️⃣ match directo
        if norm_field in norm_columns:
            mapping[field] = norm_columns[norm_field]
            continue

        for norm_col, original_col in norm_columns.items():
            if norm_field in norm_col or norm_col in norm_field:
                mapping[field] = original_col
                break

        if field in mapping:
            continue

        # 2️⃣ aliases normalizados
        for alias in ALIASES.get(field, []):
            norm_alias = normalize(alias)

            for norm_col, original_col in norm_columns.items():
                if norm_alias in norm_col:
                    mapping[field] = original_col
                    break
            if field in mapping:
                break

    return mapping

