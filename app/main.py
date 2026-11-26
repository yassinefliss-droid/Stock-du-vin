from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import assistant, auth, movements, products, stock, users
from app.deps import RedirectionLogin
from app.services.erreurs import ErreurMetier
from app.web import routes as web
from app.web.routes import STATIC_DIR

app = FastAPI(
    title="Stock en cave", version="1.0.0", description="Suivi de stock d'une cave à vins"
)

for module in (auth, products, movements, stock, users, assistant):
    app.include_router(module.router)
app.include_router(web.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.exception_handler(ErreurMetier)
def erreur_metier(request: Request, exc: ErreurMetier):
    return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)


@app.exception_handler(RedirectionLogin)
def redirection_login(request: Request, exc: RedirectionLogin):
    return RedirectResponse("/login", status_code=303)


@app.get("/health", tags=["divers"])
def health():
    return {"status": "ok"}
