from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from services.templating import templates

router = APIRouter()

# La página de carga ("/") vive en main.py: necesita el uso del mes del usuario
# Sobre nosotros: pública, con o sin cuenta
@router.get("/sobre-nosotros", response_class=HTMLResponse)
def about(request: Request):
    return templates.TemplateResponse(request, "about.html", {"request": request})
