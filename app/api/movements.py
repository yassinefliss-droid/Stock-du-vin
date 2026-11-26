from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ECRITURE, get_current_user, require_roles
from app.models import TypeMouvement, User
from app.schemas import MouvementCreate, MouvementOut
from app.services import stock as svc

router = APIRouter(prefix="/api/movements", tags=["mouvements"])


@router.post("", response_model=MouvementOut, status_code=201)
def enregistrer(
    donnees: MouvementCreate,
    user: User = Depends(require_roles(*ECRITURE)),
    db: Session = Depends(get_db),
):
    """Enregistre un mouvement. Une sortie qui rendrait le stock négatif est refusée (409)."""
    return svc.enregistrer_mouvement(
        db,
        product_id=donnees.product_id,
        type=donnees.type,
        quantite=donnees.quantite,
        date_mouvement=donnees.date,
        motif=donnees.motif,
        user_id=user.id,
    )


@router.get("", response_model=list[MouvementOut], dependencies=[Depends(get_current_user)])
def historique(
    product_id: int | None = None,
    date_debut: date | None = None,
    date_fin: date | None = None,
    type: TypeMouvement | None = None,
    limite: int = 200,
    db: Session = Depends(get_db),
):
    return svc.historique(
        db, product_id=product_id, debut=date_debut, fin=date_fin, type=type, limite=limite
    )
