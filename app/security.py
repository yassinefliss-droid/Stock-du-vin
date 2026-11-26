from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import settings

ALGO = "HS256"


def hash_password(mot_de_passe: str) -> str:
    return bcrypt.hashpw(mot_de_passe.encode(), bcrypt.gensalt()).decode()


def verify_password(mot_de_passe: str, hache: str) -> bool:
    return bcrypt.checkpw(mot_de_passe.encode(), hache.encode())


def create_token(user_id: int) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expire}, settings.secret_key, ALGO)


def decode_token(token: str) -> int | None:
    try:
        return int(jwt.decode(token, settings.secret_key, algorithms=[ALGO])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
