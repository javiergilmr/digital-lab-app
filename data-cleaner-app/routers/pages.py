from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from services.templating import templates

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request, "index.html",
        {"request": request}
    )
