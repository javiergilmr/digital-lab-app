from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from services.supabase_auth import (
    AuthError,
    exchange_code,
    google_authorize_url,
    google_enabled,
    new_pkce_pair,
    send_password_reset,
    sign_in,
    sign_out,
    sign_up,
    update_password,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

ACCESS_COOKIE = "sb_access"
REFRESH_COOKIE = "sb_refresh"
VERIFIER_COOKIE = "sb_verifier"
REFRESH_MAX_AGE = 30 * 24 * 3600
VERIFIER_MAX_AGE = 15 * 60

TITLES = {
    "login": ("Iniciar sesión", "Entra para guardar tus informes y ver tu panel."),
    "signup": ("Crear cuenta", "Crea tu cuenta para empezar."),
    "forgot": ("Recuperar contraseña", "Te enviaremos un enlace para crear una nueva contraseña."),
    "reset": ("Nueva contraseña", "Escribe tu nueva contraseña."),
}


# =========================
# COOKIES
# =========================

def _secure(request: Request):
    return request.url.scheme == "https"


def set_session_cookies(response, session, secure):
    options = {"httponly": True, "samesite": "lax", "secure": secure, "path": "/"}
    response.set_cookie(ACCESS_COOKIE, session["access_token"], max_age=session.get("expires_in", 3600), **options)
    response.set_cookie(REFRESH_COOKIE, session["refresh_token"], max_age=REFRESH_MAX_AGE, **options)


def clear_session_cookies(response):
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")


def _set_verifier(response, verifier, secure):
    response.set_cookie(VERIFIER_COOKIE, verifier, max_age=VERIFIER_MAX_AGE,
                        httponly=True, samesite="lax", secure=secure, path="/")


# =========================
# UTILIDADES
# =========================

def safe_next(value):
    # Solo rutas internas: evita que ?next= mande a otro sitio
    if value and value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value
    return "/"


def _callback_url(request: Request, next_path):
    return str(request.url_for("auth_callback").include_query_params(next=next_path))


def _render(request: Request, mode, status_code=200, **context):
    title, subtitle = TITLES[mode]
    return templates.TemplateResponse(
        request, "auth.html",
        {
            "mode": mode,
            "page_title": title,
            "subtitle": subtitle,
            "google_enabled": mode in ("login", "signup") and google_enabled(),
            "next": "/",
            "email": "",
            **context,
        },
        status_code=status_code,
    )


def _logged_in_redirect(session, next_path, secure):
    response = RedirectResponse(safe_next(next_path), status_code=303)
    set_session_cookies(response, session, secure)
    return response


# =========================
# LOGIN
# =========================

@router.get("/login")
def login_page(request: Request, next: str = "/", deleted: bool = False):
    if request.state.user:
        return RedirectResponse(safe_next(next), status_code=303)
    notice = "Tu cuenta y todos tus datos fueron eliminados." if deleted else None
    return _render(request, "login", next=safe_next(next), notice=notice)


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), next: str = Form("/")):
    try:
        session = sign_in(email.strip(), password)
    except AuthError as e:
        return _render(request, "login", status_code=400, error=e.message, email=email, next=safe_next(next))
    return _logged_in_redirect(session, next, _secure(request))


# =========================
# REGISTRO
# =========================

@router.get("/signup")
def signup_page(request: Request):
    if request.state.user:
        return RedirectResponse("/", status_code=303)
    return _render(request, "signup")


@router.post("/signup")
def signup(request: Request, email: str = Form(...), password: str = Form(...), confirm: str = Form(...)):
    email = email.strip()
    if password != confirm:
        return _render(request, "signup", status_code=400, error="Las contraseñas no coinciden.", email=email)

    verifier, challenge = new_pkce_pair()
    try:
        result = sign_up(email, password, _callback_url(request, "/"), challenge)
    except AuthError as e:
        return _render(request, "signup", status_code=400, error=e.message, email=email)

    # Si el proyecto no pide confirmar el correo, Supabase devuelve la sesión de una vez
    if "access_token" in result:
        return _logged_in_redirect(result, "/", _secure(request))

    response = _render(request, "login", email=email,
                       notice=f"Te enviamos un correo a {email} para confirmar tu cuenta. Ábrelo desde este navegador.")
    _set_verifier(response, verifier, _secure(request))
    return response


# =========================
# RECUPERAR CONTRASEÑA
# =========================

@router.get("/forgot-password")
def forgot_page(request: Request):
    return _render(request, "forgot")


@router.post("/forgot-password")
def forgot(request: Request, email: str = Form(...)):
    email = email.strip()
    verifier, challenge = new_pkce_pair()
    try:
        send_password_reset(email, _callback_url(request, "/reset-password"), challenge)
    except AuthError as e:
        if e.code in ("over_email_send_rate_limit", "over_request_rate_limit", "network", "email_address_invalid"):
            return _render(request, "forgot", status_code=400, error=e.message, email=email)

    # Mismo mensaje exista o no la cuenta, para no revelar qué correos están registrados
    response = _render(request, "login", email=email,
                       notice="Si ese correo tiene una cuenta, te enviamos un enlace para crear una nueva contraseña.")
    _set_verifier(response, verifier, _secure(request))
    return response


@router.get("/reset-password")
def reset_page(request: Request):
    return _render(request, "reset")


@router.post("/reset-password")
def reset(request: Request, password: str = Form(...), confirm: str = Form(...)):
    if password != confirm:
        return _render(request, "reset", status_code=400, error="Las contraseñas no coinciden.")
    try:
        update_password(request.state.access_token, password)
    except AuthError as e:
        return _render(request, "reset", status_code=400, error=e.message)
    return RedirectResponse("/", status_code=303)


# =========================
# GOOGLE Y ENLACES DE CORREO
# =========================

@router.get("/auth/google")
def google_login(request: Request, next: str = "/"):
    verifier, challenge = new_pkce_pair()
    response = RedirectResponse(google_authorize_url(_callback_url(request, safe_next(next)), challenge), status_code=303)
    _set_verifier(response, verifier, _secure(request))
    return response


@router.get("/auth/callback", name="auth_callback")
def auth_callback(request: Request, code: str = "", next: str = "/", error_description: str = ""):
    if error_description:
        return _render(request, "login", status_code=400, error=f"Supabase rechazó el inicio de sesión: {error_description}")

    verifier = request.cookies.get(VERIFIER_COOKIE)
    if not code or not verifier:
        # Pasa si el enlace del correo se abre en otro navegador: la cuenta sí queda confirmada
        return _render(request, "login", notice="Si estabas confirmando tu correo, ya quedó confirmado. Inicia sesión.")

    try:
        session = exchange_code(code, verifier)
    except AuthError as e:
        return _render(request, "login", status_code=400, error=e.message)

    response = _logged_in_redirect(session, next, _secure(request))
    response.delete_cookie(VERIFIER_COOKIE, path="/")
    return response


# =========================
# LOGOUT
# =========================

@router.post("/logout")
def logout(request: Request):
    if request.state.access_token:
        sign_out(request.state.access_token)
    response = RedirectResponse("/login", status_code=303)
    clear_session_cookies(response)
    return response
