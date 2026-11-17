# Motor de plantillas compartido por todas las páginas.
# asset() agrega ?v=<fecha de modificación> a los CSS y JS: cuando el archivo cambia (o se despliega
# una versión nueva), la URL cambia y el navegador descarga la nueva en lugar de usar la de su caché.
from pathlib import Path

from fastapi.templating import Jinja2Templates

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def asset(path: str) -> str:
    try:
        version = int((STATIC_DIR / path).stat().st_mtime)
    except OSError:
        version = 0
    return f"/static/{path}?v={version}"


templates = Jinja2Templates(directory="templates")
templates.env.globals["asset"] = asset
