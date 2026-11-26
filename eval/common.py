"""Base d'évaluation : SQLite temporaire + données seed ancrées à une date FIXE (reproductible)."""

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (enregistre les tables)
from app.database import Base
from app.seed import seed

ANCHOR = date(2026, 11, 25)  # « aujourd'hui » pour l'évaluation (un mercredi)


def base_eval() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    seed(db, ANCHOR)
    return db
