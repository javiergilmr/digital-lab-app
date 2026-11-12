# Cuenta del usuario en "Mi panel": método de acceso, cambio de contraseña y eliminación de la cuenta

from services.report_history import BUCKET
from services.supabase_auth import (
    AuthError, forget_token, rest_call, sign_in, sign_out, storage_list, storage_remove, update_password
)

PROVIDER_LABELS = {"email": "Correo y contraseña", "google": "Google"}


class AccountError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


def access_methods(user):
    """Cómo entra el usuario: ["email"], ["google"] o ambos."""
    meta = user.get("app_metadata") or {}
    providers = meta.get("providers") or ([meta["provider"]] if meta.get("provider") else [])
    return [{"id": p, "label": PROVIDER_LABELS.get(p, p.capitalize())} for p in providers]


def has_password(user):
    return any(m["id"] == "email" for m in access_methods(user))


def change_password(user, current, new, confirm):
    if new != confirm:
        raise AccountError("Las contraseñas nuevas no coinciden.")
    if new == current:
        raise AccountError("La nueva contraseña debe ser distinta a la actual.")

    # Se confirma la contraseña actual iniciando sesión con ella: así un tercero con
    # la sesión abierta no puede cambiarla. Esa sesión extra se cierra al terminar.
    try:
        session = sign_in(user["email"], current)
    except AuthError as e:
        if e.code == "invalid_credentials":
            raise AccountError("La contraseña actual no es correcta.") from None
        raise AccountError(e.message) from None

    try:
        update_password(session["access_token"], new)
    except AuthError as e:
        raise AccountError(e.message) from None
    finally:
        sign_out(session["access_token"])


def delete_account(user, access_token, confirm_email):
    """Borra los PDFs del usuario y luego su cuenta (stats e historial se borran en cascada)."""
    if confirm_email.strip().lower() != user["email"].lower():
        raise AccountError("Escribe tu correo exactamente como aparece para confirmar.")

    try:
        files = storage_list(BUCKET, user["id"], access_token)
        if files:
            storage_remove(BUCKET, [f"{user['id']}/{f['name']}" for f in files], access_token)
    except AuthError as e:
        # Sin bucket (reports.sql sin ejecutar) no hay PDFs que borrar; cualquier otro error detiene todo
        if "bucket not found" not in f"{e.code} {e.detail}".lower():
            print(f"⚠️ No se pudieron borrar los PDFs del usuario: {e}")
            raise AccountError("No pudimos borrar tus informes guardados. Inténtalo de nuevo.") from None

    try:
        rest_call("POST", "/rpc/delete_my_account", {}, token=access_token)
    except AuthError as e:
        print(f"⚠️ No se pudo eliminar la cuenta: {e}")
        raise AccountError("No pudimos eliminar tu cuenta. Inténtalo de nuevo más tarde.") from None

    forget_token(access_token)
