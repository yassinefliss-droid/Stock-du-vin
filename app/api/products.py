from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ECRITURE, get_current_user, require_roles
from app.models import Couleur, Product, Role, StockMovement
from app.schemas import (
    ProduitCreate,
    ProduitOut,
    ProduitStockOut,
    ProduitUpdate,
    StockProduitOut,
)
from app.services import stock as svc
from app.services.erreurs import ConflitMetier, Introuvable

router = APIRouter(
    prefix="/api/products", tags=["produits"], dependencies=[Depends(get_current_user)]
)


def _produit(db: Session, product_id: int) -> Product:
    produit = db.get(Product, product_id)
    if produit is None:
        raise Introuvable(f"Produit {product_id} introuvable")
    return produit


@router.get("", response_model=list[ProduitStockOut])
def lister(
    recherche: str | None = None,
    couleur: Couleur | None = None,
    millesime: int | None = None,
    sous_seuil: bool = False,
    db: Session = Depends(get_db),
):
    lignes = svc.lister(db, svc.Filtre(recherche, couleur, millesime), sous_seuil)
    return [
        ProduitStockOut(**ProduitOut.model_validate(x.produit).model_dump(), stock=x.stock)
        for x in lignes
    ]


@router.post(
    "", response_model=ProduitOut, status_code=201, dependencies=[Depends(require_roles(*ECRITURE))]
)
def creer(donnees: ProduitCreate, db: Session = Depends(get_db)):
    produit = Product(**donnees.model_dump())
    db.add(produit)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflitMetier(f"La référence « {donnees.reference} » existe déjà") from None
    return produit


@router.get("/{product_id}", response_model=ProduitOut)
def lire(product_id: int, db: Session = Depends(get_db)):
    return _produit(db, product_id)


@router.put(
    "/{product_id}", response_model=ProduitOut, dependencies=[Depends(require_roles(*ECRITURE))]
)
def modifier(product_id: int, donnees: ProduitUpdate, db: Session = Depends(get_db)):
    produit = _produit(db, product_id)
    for champ, valeur in donnees.model_dump(exclude_unset=True).items():
        setattr(produit, champ, valeur)
    db.commit()
    return produit


@router.delete("/{product_id}", status_code=204, dependencies=[Depends(require_roles(Role.admin))])
def supprimer(product_id: int, db: Session = Depends(get_db)):
    produit = _produit(db, product_id)
    if db.scalar(select(StockMovement.id).where(StockMovement.product_id == product_id).limit(1)):
        raise ConflitMetier("Suppression impossible : ce produit a un historique de mouvements")
    db.delete(produit)
    db.commit()


@router.get("/{product_id}/stock", response_model=StockProduitOut)
def stock_produit(product_id: int, db: Session = Depends(get_db)):
    produit = _produit(db, product_id)
    stock = svc.stock_courant(db, product_id)
    return StockProduitOut(
        product_id=product_id,
        stock=stock,
        seuil_alerte=produit.seuil_alerte,
        sous_seuil=stock <= produit.seuil_alerte,
    )
