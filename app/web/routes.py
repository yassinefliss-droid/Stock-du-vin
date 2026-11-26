"""Interface web (Jinja2, sans JavaScript). Réutilise les mêmes services que l'API."""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.auth import authentifier
from app.assistant import agent
from app.assistant.formatage import eur
from app.config import settings
from app.database import get_db
from app.deps import ECRITURE, get_web_user
from app.models import Couleur, Product, TypeMouvement, User
from app.schemas import MouvementCreate, ProduitCreate
from app.security import create_token
from app.services import stock as svc
from app.services.erreurs import ErreurMetier

BASE = Path(__file__).parent
STATIC_DIR = BASE / "static"
templates = Jinja2Templates(directory=BASE / "templates")
templates.env.filters["eur"] = lambda x: eur(float(x))
templates.env.globals["TypeMouvement"] = TypeMouvement
templates.env.globals["Couleur"] = Couleur

router = APIRouter(include_in_schema=False)


def page(request: Request, nom: str, user: User | None = None, status: int = 200, **ctx):
    return templates.TemplateResponse(
        request,
        nom,
        {"user": user, "peut_ecrire": bool(user and user.role in ECRITURE), **ctx},
        status_code=status,
    )


@router.get("/")
def accueil():
    return RedirectResponse("/dashboard")


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return page(request, "login.html")


@router.post("/login")
def login(
    request: Request, email: str = Form(), password: str = Form(), db: Session = Depends(get_db)
):
    user = authentifier(db, email, password)
    if user is None:
        return page(request, "login.html", status=401, erreur="Email ou mot de passe incorrect")
    reponse = RedirectResponse("/dashboard", status_code=303)
    reponse.set_cookie(
        "access_token",
        create_token(user.id),
        httponly=True,
        samesite="lax",
        max_age=settings.access_token_minutes * 60,
    )
    return reponse


@router.post("/logout")
def logout():
    reponse = RedirectResponse("/login", status_code=303)
    reponse.delete_cookie("access_token")
    return reponse


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, user: User = Depends(get_web_user), db: Session = Depends(get_db)):
    lignes = svc.lister(db)
    alertes = [x for x in lignes if x.stock <= x.produit.seuil_alerte]
    recents = svc.historique(db, limite=8)
    return page(
        request, "dashboard.html", user, valeur=svc.valeur(lignes), alertes=alertes, recents=recents
    )


@router.get("/produits", response_class=HTMLResponse)
def produits(
    request: Request,
    recherche: str = "",
    couleur: str = "",
    sous_seuil: bool = False,
    user: User = Depends(get_web_user),
    db: Session = Depends(get_db),
):
    filtre = svc.Filtre(recherche or None, Couleur(couleur) if couleur else None)
    lignes = svc.lister(db, filtre, sous_seuil)
    return page(
        request,
        "produits.html",
        user,
        lignes=lignes,
        recherche=recherche,
        couleur=couleur,
        sous_seuil=sous_seuil,
    )


@router.get("/produits/nouveau", response_class=HTMLResponse)
def produit_nouveau(request: Request, user: User = Depends(get_web_user)):
    return page(request, "produit_form.html", user)


@router.post("/produits/nouveau")
def produit_creer(
    request: Request,
    reference: str = Form(),
    nom: str = Form(),
    domaine: str = Form(),
    appellation: str = Form(),
    region: str = Form(),
    millesime: str = Form(""),
    couleur: str = Form(),
    format: str = Form("75cl"),
    prix_achat: str = Form(),
    prix_vente: str = Form(),
    seuil_alerte: int = Form(6),
    user: User = Depends(get_web_user),
    db: Session = Depends(get_db),
):
    if user.role not in ECRITURE:
        return page(request, "produit_form.html", user, status=403, erreur="Droits insuffisants")
    try:
        donnees = ProduitCreate(
            reference=reference,
            nom=nom,
            domaine=domaine,
            appellation=appellation,
            region=region,
            millesime=int(millesime) if millesime else None,
            couleur=couleur,
            format=format,
            prix_achat=prix_achat,
            prix_vente=prix_vente,
            seuil_alerte=seuil_alerte,
        )
    except (ValidationError, ValueError) as e:
        return page(
            request, "produit_form.html", user, status=422, erreur=f"Données invalides : {e}"
        )
    if db.query(Product).filter_by(reference=donnees.reference).first():
        return page(
            request, "produit_form.html", user, status=409, erreur="Référence déjà utilisée"
        )
    produit = Product(**donnees.model_dump())
    db.add(produit)
    db.commit()
    return RedirectResponse(f"/produits/{produit.id}", status_code=303)


@router.get("/produits/{product_id}", response_class=HTMLResponse)
def produit_fiche(
    request: Request,
    product_id: int,
    user: User = Depends(get_web_user),
    db: Session = Depends(get_db),
):
    produit = db.get(Product, product_id)
    if produit is None:
        return page(request, "erreur.html", user, status=404, message="Produit introuvable")
    return page(
        request,
        "produit_fiche.html",
        user,
        produit=produit,
        stock=svc.stock_courant(db, product_id),
        mouvements=svc.historique(db, product_id=product_id, limite=100),
    )


@router.get("/mouvements/nouveau", response_class=HTMLResponse)
def mouvement_form(
    request: Request,
    product_id: int | None = None,
    user: User = Depends(get_web_user),
    db: Session = Depends(get_db),
):
    return page(request, "mouvement_form.html", user, lignes=svc.lister(db), product_id=product_id)


@router.post("/mouvements/nouveau")
def mouvement_creer(
    request: Request,
    product_id: int = Form(),
    type: str = Form(),
    quantite: int = Form(),
    motif: str = Form(""),
    date: str = Form(""),
    user: User = Depends(get_web_user),
    db: Session = Depends(get_db),
):
    def erreur(message: str, status: int):
        return page(
            request,
            "mouvement_form.html",
            user,
            status=status,
            erreur=message,
            lignes=svc.lister(db),
            product_id=product_id,
        )

    if user.role not in ECRITURE:
        return erreur("Droits insuffisants : votre rôle est en lecture seule.", 403)
    try:
        donnees = MouvementCreate(
            product_id=product_id,
            type=type,
            quantite=quantite,
            motif=motif,
            date=datetime.fromisoformat(date) if date else None,
        )
        svc.enregistrer_mouvement(
            db,
            product_id=donnees.product_id,
            type=donnees.type,
            quantite=donnees.quantite,
            date_mouvement=donnees.date,
            motif=donnees.motif,
            user_id=user.id,
        )
    except ErreurMetier as e:
        return erreur(str(e), e.status_code)
    except (ValidationError, ValueError) as e:
        return erreur(f"Données invalides : {e}", 422)
    return RedirectResponse(f"/produits/{product_id}", status_code=303)


@router.get("/assistant", response_class=HTMLResponse)
def assistant_form(request: Request, user: User = Depends(get_web_user)):
    return page(request, "assistant.html", user)


@router.post("/assistant", response_class=HTMLResponse)
def assistant_poser(
    request: Request,
    question: str = Form(),
    user: User = Depends(get_web_user),
    db: Session = Depends(get_db),
):
    return page(
        request, "assistant.html", user, question=question, reponse=agent.repondre(db, question)
    )
