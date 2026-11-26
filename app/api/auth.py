from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import Token, UserOut
from app.security import create_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def authentifier(db: Session, email: str, mot_de_passe: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user and user.actif and verify_password(mot_de_passe, user.password_hash):
        return user
    return None


@router.post("/token", response_model=Token)
def token(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Connexion : `username` = email. Utilisable depuis le bouton « Authorize » de Swagger."""
    user = authentifier(db, form.username, form.password)
    if user is None:
        raise HTTPException(401, "Email ou mot de passe incorrect")
    return Token(access_token=create_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
