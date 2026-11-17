# Sesiones en memoria: una por archivo subido. Expiran tras SESSION_TTL sin uso
# para que la memoria del servidor no crezca sin límite.
import time
import uuid

SESSION_TTL = 2 * 60 * 60  # segundos
SESSIONS = {}

def purge_expired_sessions():
    now = time.monotonic()
    # list() copia las llaves: otras peticiones pueden crear sesiones mientras se recorre
    for session_id, session in list(SESSIONS.items()):
        if now - session["last_used"] > SESSION_TTL:
            SESSIONS.pop(session_id, None)

def create_session(df, schema, owner_id, filename=""):
    purge_expired_sessions()
    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {
        "last_used": time.monotonic(),
        "df": df,
        "df_original": df.copy(),
        "schema": schema,
        "report_name": "",
        "filename": filename,
        "clean_report": None,
        "owner_id": owner_id
    }
    return session_id

def _get_session(session_id: str, owner_id: str):
    # Otro usuario no puede ver la sesión aunque conozca su id
    session = SESSIONS.get(session_id)
    if not session or session["owner_id"] != owner_id:
        return None
    if time.monotonic() - session["last_used"] > SESSION_TTL:
        SESSIONS.pop(session_id, None)
        return None
    session["last_used"] = time.monotonic()
    return session

def get_session_df(session_id: str, owner_id: str):
    session = _get_session(session_id, owner_id)
    if not session:
        return None
    return session["df"]

def update_session_df(session_id, owner_id, df):
    session = _get_session(session_id, owner_id)
    if session:
        session["df"] = df

def set_session_mapped_df(session_id, owner_id, df):
    # Se guarda aparte para que limpiar otra vez (ej. al recargar) parta de los datos sin limpiar
    session = _get_session(session_id, owner_id)
    if session:
        session["df_mapped"] = df
        session["df"] = df

def set_session_mapping(session_id, owner_id, mapping):
    # {campo: columna} elegido en /map: al volver a mapear se muestra lo mismo que se dejó
    session = _get_session(session_id, owner_id)
    if session:
        session["mapping"] = mapping

def get_session_mapping(session_id: str, owner_id: str):
    session = _get_session(session_id, owner_id)
    return session.get("mapping") if session else None

def get_session_mapped_df(session_id: str, owner_id: str):
    session = _get_session(session_id, owner_id)
    if not session:
        return None
    return session.get("df_mapped", session["df"])

def claim_once(session_id, owner_id, key) -> bool:
    """True solo la primera vez para cada key: procesar de nuevo (ej. al recargar)
    no vuelve a sumar a los stats ni repite el informe en el historial."""
    session = _get_session(session_id, owner_id)
    if not session or session.get(key):
        return False
    session[key] = True
    return True

def set_session_clean_report(session_id, owner_id, report):
    session = _get_session(session_id, owner_id)
    if session:
        session["clean_report"] = report

def get_session_clean_report(session_id: str, owner_id: str):
    session = _get_session(session_id, owner_id)
    return session["clean_report"] if session else None

def get_session_filename(session_id: str, owner_id: str):
    session = _get_session(session_id, owner_id)
    return session["filename"] if session else ""

def get_session_original_df(session_id: str, owner_id: str):
    session = _get_session(session_id, owner_id)
    if not session:
        return None
    return session["df_original"]

def set_session_report_name(session_id, owner_id, report_name):
    session = _get_session(session_id, owner_id)
    if session:
        session["report_name"] = report_name

def get_session_report_name(session_id: str, owner_id: str):
    session = _get_session(session_id, owner_id)
    if not session:
        return ""
    return session["report_name"]
