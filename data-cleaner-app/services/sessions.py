import uuid
SESSIONS = {}

def create_session(df, schema):
    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {
        "df": df,
        "df_original": df.copy(),
        "schema": schema
    }
    # print("CREATE_SESSION")
    # print("SESSION_ID:", session_id)
    # print("DF COLUMNS:", df.columns)
    # print("SESSIONS KEYS:", SESSIONS.keys())
    return session_id

def get_session_df(session_id: str):
    session = SESSIONS.get(session_id)
    if not session:
        return None
    return session["df"]

def update_session_df(session_id, df):
    if session_id in SESSIONS:
        SESSIONS[session_id]["df"] = df

def get_session_original_df(session_id: str):
    session = SESSIONS.get(session_id)
    if not session:
        return None
    return session["df_original"]

