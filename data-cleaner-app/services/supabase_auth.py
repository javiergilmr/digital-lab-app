# app/services/supabase_auth.py
# Habla directo con la API de autenticación de Supabase (GoTrue) usando solo la librería estándar.

import base64
import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

# El .env vive en la raíz del repositorio (digita-lab-app/.env)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_PUBLISHABLE_KEY en el archivo .env")

USER_CACHE_SECONDS = 60
SETTINGS_CACHE_SECONDS = 300

ERROR_MESSAGES = {
    "invalid_credentials": "Correo o contraseña incorrectos.",
    "email_not_confirmed": "Confirma tu correo antes de iniciar sesión. Revisa tu bandeja de entrada.",
    "user_already_exists": "Ya existe una cuenta con ese correo. Inicia sesión.",
    "email_exists": "Ya existe una cuenta con ese correo. Inicia sesión.",
    "weak_password": "La contraseña es muy débil. Usa al menos 6 caracteres.",
    "same_password": "La nueva contraseña debe ser distinta a la anterior.",
    "email_address_invalid": "Ese correo no es válido.",
    "validation_failed": "Revisa que el correo y la contraseña sean válidos.",
    "signup_disabled": "El registro de cuentas está desactivado.",
    "over_email_send_rate_limit": "Se enviaron demasiados correos. Espera unos minutos e inténtalo de nuevo.",
    "over_request_rate_limit": "Demasiados intentos. Espera unos minutos e inténtalo de nuevo.",
    "flow_state_not_found": "El enlace ya se usó o expiró. Solicita uno nuevo.",
    "flow_state_expired": "El enlace ya se usó o expiró. Solicita uno nuevo.",
    "bad_code_verifier": "No pudimos completar el inicio de sesión en este navegador.",
    "network": "No se pudo conectar con Supabase. Revisa tu conexión e inténtalo de nuevo.",
}


class AuthError(Exception):
    def __init__(self, code="", detail="", status=0):
        self.code = code
        self.detail = detail
        self.status = status
        super().__init__(f"{status} {code} {detail}")

    @property
    def message(self):
        return ERROR_MESSAGES.get(self.code, "No se pudo completar la operación. Inténtalo de nuevo.")


def _call(method, path, body=None, token=None, query=None, api="auth", content_type=None, binary=False):
    """api="auth" es Supabase Auth, "rest" la API de datos y "storage" los archivos.
    body puede ser un dict (se envía como JSON) o bytes con su content_type; binary=True devuelve bytes."""
    url = f"{SUPABASE_URL}/{api}/v1{path}"
    if query:
        url += "?" + urlencode(query)

    headers = {"apikey": SUPABASE_KEY, "Content-Type": content_type or "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    if isinstance(body, bytes):
        data = body
    else:
        data = json.dumps(body).encode() if body is not None else None

    try:
        with urlopen(Request(url, data=data, headers=headers, method=method), timeout=20) as res:
            raw = res.read()
            if binary:
                return raw
            return json.loads(raw) if raw else {}
    except HTTPError as e:
        try:
            info = json.loads(e.read() or b"{}")
        except ValueError:
            info = {}
        if not isinstance(info, dict):
            info = {}
        code = info.get("error_code") or info.get("error") or info.get("code") or ""
        detail = info.get("msg") or info.get("error_description") or info.get("message") or ""
        raise AuthError(code, detail, e.code) from None
    except URLError:
        raise AuthError("network") from None


def rest_call(method, path, body=None, token=None, query=None):
    """Llama a la API de datos como el usuario del token: las políticas RLS se aplican a su nombre."""
    return _call(method, path, body, token, query, api="rest")


def storage_upload(bucket, path, data, content_type, token):
    """Sube un archivo a Supabase Storage como el usuario del token (aplican las políticas del bucket)."""
    _call("POST", f"/object/{bucket}/{path}", data, token, api="storage", content_type=content_type)


def storage_download(bucket, path, token) -> bytes:
    return _call("GET", f"/object/authenticated/{bucket}/{path}", token=token, api="storage", binary=True)


def storage_list(bucket, prefix, token):
    """Archivos dentro de una carpeta del bucket (solo los que las políticas dejan ver)."""
    return _call("POST", f"/object/list/{bucket}", {"prefix": prefix, "limit": 1000, "offset": 0}, token, api="storage")


def storage_remove(bucket, paths, token):
    _call("DELETE", f"/object/{bucket}", {"prefixes": paths}, token, api="storage")


# =========================
# PKCE: Google y los enlaces por correo vuelven con ?code=, que se canjea con este verificador
# =========================

def new_pkce_pair():
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def _pkce(challenge):
    return {"code_challenge": challenge, "code_challenge_method": "s256"}


# =========================
# OPERACIONES
# =========================

def sign_in(email, password):
    return _call("POST", "/token", {"email": email, "password": password}, query={"grant_type": "password"})


def sign_up(email, password, redirect_to, challenge):
    return _call("POST", "/signup", {"email": email, "password": password, **_pkce(challenge)},
                 query={"redirect_to": redirect_to})


def send_password_reset(email, redirect_to, challenge):
    _call("POST", "/recover", {"email": email, **_pkce(challenge)}, query={"redirect_to": redirect_to})


def exchange_code(code, verifier):
    return _call("POST", "/token", {"auth_code": code, "code_verifier": verifier}, query={"grant_type": "pkce"})


def refresh_session(refresh_token):
    return _call("POST", "/token", {"refresh_token": refresh_token}, query={"grant_type": "refresh_token"})


def update_password(access_token, password):
    _call("PUT", "/user", {"password": password}, token=access_token)
    forget_token(access_token)


def sign_out(access_token):
    forget_token(access_token)
    try:
        _call("POST", "/logout", token=access_token, query={"scope": "local"})
    except AuthError:
        pass  # La sesión ya no era válida: igual se borran las cookies


def google_authorize_url(redirect_to, challenge):
    query = {"provider": "google", "redirect_to": redirect_to, **_pkce(challenge)}
    return f"{SUPABASE_URL}/auth/v1/authorize?{urlencode(query)}"


# =========================
# VALIDAR SESIÓN (con caché corta para no llamar a Supabase en cada petición)
# =========================

_user_cache = {}


def _token_key(token):
    return hashlib.sha256(token.encode()).hexdigest()


def forget_token(access_token):
    _user_cache.pop(_token_key(access_token), None)


def get_user(access_token):
    """Devuelve el usuario dueño del token, o None si el token no es válido."""
    key = _token_key(access_token)
    cached = _user_cache.get(key)
    if cached and cached[1] > time.time():
        return cached[0]

    try:
        user = _call("GET", "/user", token=access_token)
    except AuthError:
        _user_cache.pop(key, None)
        return None

    # Se descartan entradas vencidas para que la caché no crezca sin límite
    now = time.time()
    for k in [k for k, (_, until) in _user_cache.items() if until <= now]:
        del _user_cache[k]

    _user_cache[key] = (user, now + USER_CACHE_SECONDS)
    return user


_settings_cache = {"value": None, "until": 0}


def google_enabled():
    if _settings_cache["until"] < time.time():
        try:
            settings = _call("GET", "/settings")
            _settings_cache["value"] = bool(settings.get("external", {}).get("google"))
        except AuthError:
            _settings_cache["value"] = False
        _settings_cache["until"] = time.time() + SETTINGS_CACHE_SECONDS
    return _settings_cache["value"]
