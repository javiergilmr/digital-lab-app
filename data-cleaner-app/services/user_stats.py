# Stats del panel de usuario: se guardan en la tabla user_stats de Supabase (ver supabase/user_stats.sql)

from services.supabase_auth import AuthError, rest_call

PLANS = {"free": "Gratuito"}

EMPTY_STATS = {
    "files_uploaded": 0,
    "rows_processed": 0,
    "rows_fixed": 0,
    "rows_removed": 0,
    "plan": "free",
}


class StatsUnavailable(Exception):
    pass


def record_activity(access_token, files=0, processed=0, fixed=0, removed=0):
    """Suma actividad al usuario del token. Si falla, solo se avisa en consola: nunca frena al usuario."""
    try:
        rest_call("POST", "/rpc/record_activity", {
            "files": int(files),
            "processed": int(processed),
            "fixed": int(fixed),
            "removed": int(removed),
        }, token=access_token)
    except AuthError as e:
        print(f"⚠️ No se pudieron guardar los stats del usuario: {e}")


def get_stats(access_token, user_id):
    """Stats del usuario; si todavía no tiene actividad, todo en 0 con plan gratuito."""
    try:
        rows = rest_call("GET", "/user_stats", token=access_token, query={
            "select": "files_uploaded,rows_processed,rows_fixed,rows_removed,plan",
            "user_id": f"eq.{user_id}",
        })
    except AuthError as e:
        print(f"⚠️ No se pudieron leer los stats del usuario: {e}")
        raise StatsUnavailable() from None

    stats = {**EMPTY_STATS, **(rows[0] if rows else {})}
    stats["plan_label"] = PLANS.get(stats["plan"], stats["plan"].capitalize())
    return stats
