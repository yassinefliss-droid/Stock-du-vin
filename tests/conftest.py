from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import Couleur, Product, Role, StockMovement, TypeMouvement, User
from app.security import create_token, hash_password

AUJOURDHUI = date(2025, 6, 18)  # un mercredi : semaine dernière = 9 → 15 juin


@pytest.fixture
def db():
    engine = create_engine(  # base SQLite en mémoire, neuve pour chaque test
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session


@pytest.fixture(autouse=True)
def date_figee(monkeypatch):
    monkeypatch.setattr(settings, "assistant_today", AUJOURDHUI)
    monkeypatch.setattr(settings, "llm_provider", "none")
    monkeypatch.setattr(settings, "secret_key", "cle-de-test-" + "x" * 32)


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, follow_redirects=False) as c:
        yield c
    app.dependency_overrides.clear()


HASH = hash_password("motdepasse1")  # calculé une fois : bcrypt est volontairement lent


def _user(db, email, role):
    user = User(email=email, password_hash=HASH, role=role)
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def users(db):
    return {r: _user(db, f"{r.value}@test.fr", r) for r in Role}


@pytest.fixture
def auth(users):
    """auth[Role.admin] → en-têtes HTTP avec un jeton valide pour ce rôle."""
    return {r: {"Authorization": f"Bearer {create_token(u.id)}"} for r, u in users.items()}


def produit(db, ref, nom, appellation, region, couleur, millesime, achat, vente, seuil=5):
    p = Product(reference=ref, nom=nom, domaine=nom, appellation=appellation, region=region,
                couleur=couleur, millesime=millesime, prix_achat=achat, prix_vente=vente,
                seuil_alerte=seuil)  # fmt: skip
    db.add(p)
    db.commit()
    return p


def mouvement(db, p, type_, q, jour, motif=""):
    m = StockMovement(product_id=p.id, type=type_, quantite=q, motif=motif,
                      date=datetime.combine(jour, datetime.min.time().replace(hour=10)))  # fmt: skip
    db.add(m)
    db.commit()


@pytest.fixture
def cave(db):
    """Petit jeu de données dont tous les chiffres sont calculables de tête.

    Figeac 2018 : 20 − 5 (sortie 12/06) + 2 (ajust.) = 17 ; Angélus 2018 : 4 − 1 = 3 (≤ seuil 5)
    Chablis 2020 : 10 (blanc, 0 sortie) ; Krug NM : 6 − 2 (sortie 11/06) = 4 (≤ seuil 5)
    """
    figeac = produit(db, "FIG-18", "Château Figeac", "Saint-Émilion Grand Cru", "Bordeaux",
                     Couleur.rouge, 2018, 100, 150)  # fmt: skip
    angelus = produit(db, "ANG-18", "Château Angélus", "Saint-Émilion Grand Cru", "Bordeaux",
                      Couleur.rouge, 2018, 200, 300)  # fmt: skip
    chablis = produit(db, "CHA-20", "Chablis La Forest", "Chablis", "Bourgogne",
                      Couleur.blanc, 2020, 40, 60)  # fmt: skip
    krug = produit(db, "KRU-NM", "Krug Grande Cuvée", "Champagne", "Champagne",
                   Couleur.effervescent, None, 140, 200)  # fmt: skip
    E, S, A = TypeMouvement.entree, TypeMouvement.sortie, TypeMouvement.ajustement
    mouvement(db, figeac, E, 20, date(2025, 3, 1), "Stock initial")
    mouvement(db, figeac, S, 5, date(2025, 6, 12), "Vente")
    mouvement(db, figeac, A, 2, date(2025, 6, 16), "Inventaire")
    mouvement(db, angelus, E, 4, date(2025, 3, 1))
    mouvement(db, angelus, S, 1, date(2025, 6, 17), "Vente")
    mouvement(db, chablis, E, 10, date(2025, 3, 1))
    mouvement(db, krug, E, 6, date(2025, 3, 1))
    mouvement(db, krug, S, 2, date(2025, 6, 11), "Vente")
    return {"figeac": figeac, "angelus": angelus, "chablis": chablis, "krug": krug}
