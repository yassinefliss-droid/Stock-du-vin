"""Authentification (JWT en en-tête Bearer ou en cookie) et contrôle des rôles."""

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Role, User
from app.security import decode_token

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

ECRITURE = (Role.admin, Role.gestionnaire)


class RedirectionLogin(Exception):
    """Levée côté web quand l'utilisateur n'est pas connecté."""


def utilisateur_depuis_token(db: Session, token: str | None) -> User | None:
    user_id = decode_token(token) if token else None
    user = db.get(User, user_id) if user_id else None
    return user if user and user.actif else None


def get_current_user(
    request: Request, token: str | None = Depends(oauth2), db: Session = Depends(get_db)
) -> User:
    user = utilisateur_depuis_token(db, token or request.cookies.get("access_token"))
    if user is None:
        raise HTTPException(401, "Non authentifié", headers={"WWW-Authenticate": "Bearer"})
    return user


def require_roles(*roles: Role):
    def verifier(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Droits insuffisants pour cette action")
        return user

    return verifier


def get_web_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = utilisateur_depuis_token(db, request.cookies.get("access_token"))
    if user is None:
        raise RedirectionLogin()
    return user
