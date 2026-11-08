import uuid
SESSIONS = {}

def create_session(df, schema, owner_id):
    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {
        "df": df,
        "df_original": df.copy(),
        "schema": schema,
        "report_name": "",
        "owner_id": owner_id
    }
    # print("CREATE_SESSION")
    # print("SESSION_ID:", session_id)
    # print("DF COLUMNS:", df.columns)
    # print("SESSIONS KEYS:", SESSIONS.keys())
    return session_id

def _get_session(session_id: str, owner_id: str):
    # Otro usuario no puede ver la sesión aunque conozca su id
    session = SESSIONS.get(session_id)
    if not session or session["owner_id"] != owner_id:
        return None
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

def get_session_mapped_df(session_id: str, owner_id: str):
    session = _get_session(session_id, owner_id)
    if not session:
        return None
    return session.get("df_mapped", session["df"])

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
