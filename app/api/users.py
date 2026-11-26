from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import Role, User
from app.schemas import UserCreate, UserOut, UserUpdate
from app.security import hash_password
from app.services.erreurs import ConflitMetier, Introuvable

router = APIRouter(
    prefix="/api/users", tags=["utilisateurs"], dependencies=[Depends(require_roles(Role.admin))]
)


@router.get("", response_model=list[UserOut])
def lister(db: Session = Depends(get_db)):
    return list(db.scalars(select(User).order_by(User.email)))


@router.post("", response_model=UserOut, status_code=201)
def creer(donnees: UserCreate, db: Session = Depends(get_db)):
    user = User(
        email=donnees.email.lower(),
        password_hash=hash_password(donnees.password),
        role=donnees.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflitMetier("Cet email est déjà utilisé") from None
    return user


@router.patch("/{user_id}", response_model=UserOut)
def modifier(user_id: int, donnees: UserUpdate, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise Introuvable("Utilisateur introuvable")
    if donnees.role is not None:
        user.role = donnees.role
    if donnees.actif is not None:
        user.actif = donnees.actif
    if donnees.password:
        user.password_hash = hash_password(donnees.password)
    db.commit()
    return user
