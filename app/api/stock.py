from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.products import lister as lister_produits
from app.database import get_db
from app.deps import get_current_user
from app.models import Couleur
from app.schemas import ProduitStockOut, ValeurOut
from app.services import stock as svc

router = APIRouter(prefix="/api/stock", tags=["stock"], dependencies=[Depends(get_current_user)])


@router.get("/alertes", response_model=list[ProduitStockOut])
def alertes(db: Session = Depends(get_db)):
    """Produits dont le stock a atteint ou franchi le seuil d'alerte."""
    return lister_produits(sous_seuil=True, db=db)


@router.get("/valeur", response_model=ValeurOut)
def valeur(
    couleur: Couleur | None = None, recherche: str | None = None, db: Session = Depends(get_db)
):
    """Valeur du stock au prix d'achat et au prix de vente."""
    return svc.valeur(svc.lister(db, svc.Filtre(recherche, couleur)))
