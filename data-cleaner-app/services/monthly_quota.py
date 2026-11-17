# Límite de uso de la demo: 10 archivos por mes, se reinicia el día 1 (ver supabase/monthly_usage.sql)
# Con cuenta, el contador vive en Supabase; sin cuenta, en memoria por invitado.
# Los datos de ejemplo no cuentan.

import logging
import threading
from datetime import datetime, timezone

from services.analyzer import MONTHS
from services.supabase_auth import AuthError, rest_call

log = logging.getLogger(__name__)

MONTHLY_FILES = 10


class QuotaExceeded(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


def current_month():
    """Primer día del mes en UTC (el mismo que usa Supabase en monthly_usage.sql)."""
    return datetime.now(timezone.utc).date().replace(day=1)


def reset_text():
    month = current_month()
    reset = month.replace(year=month.year + 1, month=1) if month.month == 12 else month.replace(month=month.month + 1)
    return f"1 de {MONTHS[reset.month - 1]}"


def limit_message():
    return (
        f"Llegaste al límite de {MONTHLY_FILES} archivos de este mes. "
        f"Se reinicia el {reset_text()}. Mientras tanto puedes probar con los datos de ejemplo."
    )


# =========================
# CON CUENTA (Supabase)
# =========================

def _account_used(access_token, user_id):
    """Archivos de este mes, o None si no se pudo leer (monthly_usage.sql sin ejecutar o sin conexión)."""
    try:
        rows = rest_call("GET", "/monthly_usage", token=access_token, query={
            "select": "files_uploaded",
            "user_id": f"eq.{user_id}",
            "month": f"eq.{current_month().isoformat()}",
        })
    except AuthError as e:
        log.warning(f"No se pudo leer el uso mensual: {e}")
        return None
    return rows[0]["files_uploaded"] if rows else 0


def _account_claim(access_token):
    """Suma un archivo si queda cupo (en una sola operación, sin carreras). None si Supabase falla."""
    try:
        return bool(rest_call("POST", "/rpc/claim_monthly_file", {"max_files": MONTHLY_FILES}, token=access_token))
    except AuthError as e:
        log.warning(f"No se pudo sumar el archivo al uso mensual: {e}")
        return None


# =========================
# INVITADOS (memoria)
# =========================
# Se pierde al reiniciar el servidor: es un freno razonable para una demo, no una barrera.

_guest_usage = {}  # guest_id -> (mes, archivos)
_guest_lock = threading.Lock()


def _guest_used(guest_id):
    month, used = _guest_usage.get(guest_id, (None, 0))
    return used if month == current_month() else 0


def _guest_claim(guest_id):
    with _guest_lock:
        used = _guest_used(guest_id)
        if used >= MONTHLY_FILES:
            return False
        # Al cambiar de mes se descartan los contadores viejos
        month = current_month()
        for key in [k for k, (m, _) in _guest_usage.items() if m != month]:
            del _guest_usage[key]
        _guest_usage[guest_id] = (month, used + 1)
        return True


# =========================
# API
# =========================

def get_usage(user, access_token, guest_id):
    """Uso de este mes para mostrar en pantalla; used = None si no se pudo leer."""
    if user:
        used = _account_used(access_token, user["id"])
    else:
        used = _guest_used(guest_id) if guest_id else 0
    remaining = None if used is None else max(0, MONTHLY_FILES - used)
    return {
        "used": used,
        "limit": MONTHLY_FILES,
        "remaining": remaining,
        "pct": 0 if used is None else min(100, round(used / MONTHLY_FILES * 100)),
        "reset": reset_text(),
    }


def claim_file(user, access_token, guest_id):
    """Cuenta un archivo del mes o lanza QuotaExceeded. Si Supabase falla, deja pasar: nunca frena por un error nuestro."""
    claimed = _account_claim(access_token) if user else _guest_claim(guest_id)
    if claimed is False:
        raise QuotaExceeded(limit_message())
