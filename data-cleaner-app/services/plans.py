# Planes Gratuito y Pro: límites, plan del usuario y cupo mensual (ver supabase/plans.sql)

from datetime import date

from services.analyzer import MONTHS
from services.supabase_auth import AuthError, rest_call

# monthly_files = None es ilimitado
PLANS = {
    "free": {"label": "Gratuito", "monthly_files": 5, "max_rows": 5_000, "history": 5, "watermark": True},
    "pro": {"label": "Pro", "monthly_files": None, "max_rows": 200_000, "history": 100, "watermark": False},
}
DEFAULT_PLAN = "free"


class PlanLimitError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


def plan_info(plan_id):
    return {"id": plan_id, **PLANS.get(plan_id, PLANS[DEFAULT_PLAN])}


def get_plan(access_token, user_id):
    """Plan del usuario (de user_stats). Sin fila o si Supabase no responde, es Gratuito."""
    try:
        rows = rest_call("GET", "/user_stats", token=access_token, query={
            "select": "plan",
            "user_id": f"eq.{user_id}",
        })
    except AuthError as e:
        print(f"⚠️ No se pudo leer el plan del usuario: {e}")
        rows = []
    plan_id = rows[0]["plan"] if rows else DEFAULT_PLAN
    return plan_info(plan_id if plan_id in PLANS else DEFAULT_PLAN)


# =========================
# CUPO MENSUAL (se reinicia el día 1)
# =========================

def current_month(today=None):
    return (today or date.today()).replace(day=1)


def next_reset(today=None):
    month = current_month(today)
    return month.replace(year=month.year + 1, month=1) if month.month == 12 else month.replace(month=month.month + 1)


def reset_text(today=None):
    reset = next_reset(today)
    return f"1 de {MONTHS[reset.month - 1]}"


def get_monthly_usage(access_token, user_id):
    """Archivos procesados este mes, o None si no se pudo leer (plans.sql sin ejecutar o sin conexión)."""
    try:
        rows = rest_call("GET", "/monthly_usage", token=access_token, query={
            "select": "files_processed",
            "user_id": f"eq.{user_id}",
            "month": f"eq.{current_month().isoformat()}",
        })
    except AuthError as e:
        print(f"⚠️ No se pudo leer el uso mensual: {e}")
        return None
    return rows[0]["files_processed"] if rows else 0


def record_processed_file(access_token):
    try:
        rest_call("POST", "/rpc/record_processed_file", {"usage_month": current_month().isoformat()}, token=access_token)
    except AuthError as e:
        print(f"⚠️ No se pudo sumar el archivo al uso mensual: {e}")


# =========================
# VALIDACIONES
# =========================

def check_rows(plan, rows):
    if rows > plan["max_rows"]:
        message = (
            f"Tu plan {plan['label']} permite archivos de hasta {plan['max_rows']:,} filas "
            f"y este tiene {rows:,}. Divide el archivo en partes más pequeñas"
        )
        if plan["id"] == "free":
            message += f" o cámbiate a Pro, que permite hasta {PLANS['pro']['max_rows']:,} filas."
        else:
            message += "."
        raise PlanLimitError(message)


def check_monthly_quota(plan, used):
    """used = None (no se pudo leer) deja pasar: un fallo de Supabase no debe frenar al usuario."""
    limit = plan["monthly_files"]
    if limit is None or used is None or used < limit:
        return
    raise PlanLimitError(
        f"Ya usaste los {limit} archivos de este mes del plan {plan['label']}. "
        f"Tu cupo se reinicia el {reset_text()}. Con Pro procesas archivos ilimitados."
    )


def usage_summary(plan, used):
    """Datos del cupo para el panel."""
    limit = plan["monthly_files"]
    return {
        "used": used,
        "limit": limit,
        "pct": min(100, round(used / limit * 100)) if limit and used is not None else 0,
        "reset": reset_text(),
    }
