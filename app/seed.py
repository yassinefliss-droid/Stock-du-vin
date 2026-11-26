"""Données de démonstration : ~60 vins français, 3 utilisateurs, ~600 mouvements sur 6 mois.

    python -m app.seed [--reset] [--anchor AAAA-MM-JJ]

Déterministe (graine fixe) : mêmes vins, mêmes quantités. Les dates sont relatives à la date
d'ancrage (aujourd'hui par défaut), pour que « la semaine dernière » ait toujours des données.
"""

import argparse
import random
from datetime import date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Product, Role, StockMovement, TypeMouvement, User
from app.security import hash_password

R, B, RO, E = "rouge", "blanc", "rose", "effervescent"
BDX, BGN, RHO, LOI, CHA, ALS, LAN, PRO, SUO, BEA = (
    "Bordeaux",
    "Bourgogne",
    "Vallée du Rhône",
    "Vallée de la Loire",
    "Champagne",
    "Alsace",
    "Languedoc-Roussillon",
    "Provence",
    "Sud-Ouest",
    "Beaujolais",
)

# (domaine, nom de la cuvée, appellation, région, couleur, millésime, prix achat, prix vente, format)
VINS = [
    ("Château Lynch-Bages", "Château Lynch-Bages", "Pauillac", BDX, R, 2016, 78, 119, "75cl"),
    (
        "Château Pichon Baron",
        "Château Pichon Longueville Baron",
        "Pauillac",
        BDX,
        R,
        2015,
        82,
        125,
        "75cl",
    ),
    (
        "Château Léoville-Barton",
        "Château Léoville-Barton",
        "Saint-Julien",
        BDX,
        R,
        2014,
        65,
        99,
        "75cl",
    ),
    ("Château Talbot", "Château Talbot", "Saint-Julien", BDX, R, 2017, 38, 59, "75cl"),
    (
        "Château Cos d'Estournel",
        "Château Cos d'Estournel",
        "Saint-Estèphe",
        BDX,
        R,
        2012,
        90,
        138,
        "75cl",
    ),
    ("Château Montrose", "Château Montrose", "Saint-Estèphe", BDX, R, 2018, 85, 130, "75cl"),
    ("Château Giscours", "Château Giscours", "Margaux", BDX, R, 2016, 52, 79, "75cl"),
    ("Château Rauzan-Ségla", "Château Rauzan-Ségla", "Margaux", BDX, R, 2015, 68, 105, "75cl"),
    (
        "Château Angélus",
        "Château Angélus",
        "Saint-Émilion Grand Cru",
        BDX,
        R,
        2018,
        180,
        270,
        "75cl",
    ),
    ("Château Figeac", "Château Figeac", "Saint-Émilion Grand Cru", BDX, R, 2018, 95, 145, "75cl"),
    ("Château Canon", "Château Canon", "Saint-Émilion Grand Cru", BDX, R, 2016, 70, 108, "75cl"),
    (
        "Château Larcis Ducasse",
        "Château Larcis Ducasse",
        "Saint-Émilion Grand Cru",
        BDX,
        R,
        2019,
        48,
        75,
        "75cl",
    ),
    (
        "Château Bellevue",
        "Château Bellevue",
        "Saint-Émilion Grand Cru",
        BDX,
        R,
        2015,
        28,
        45,
        "75cl",
    ),
    ("Château Pétrus", "Pétrus", "Pomerol", BDX, R, 2010, 2400, 3100, "75cl"),
    ("Château Clinet", "Château Clinet", "Pomerol", BDX, R, 2016, 55, 85, "75cl"),
    (
        "Château Smith Haut Lafitte",
        "Château Smith Haut Lafitte",
        "Pessac-Léognan",
        BDX,
        B,
        2019,
        62,
        95,
        "75cl",
    ),
    ("Château Carbonnieux", "Château Carbonnieux", "Pessac-Léognan", BDX, B, 2020, 22, 36, "75cl"),
    ("Château d'Yquem", "Château d'Yquem", "Sauternes", BDX, B, 2015, 260, 360, "75cl"),
    ("Château Gloria", "Château Gloria", "Saint-Julien", BDX, R, 2016, 32, 49, "Magnum"),
    ("Domaine de la Romanée-Conti", "La Tâche", "La Tâche", BGN, R, 2017, 3500, 4600, "75cl"),
    (
        "Domaine Leflaive",
        "Puligny-Montrachet 1er Cru Les Pucelles",
        "Puligny-Montrachet",
        BGN,
        B,
        2018,
        280,
        390,
        "75cl",
    ),
    ("Domaine Leflaive", "Bourgogne Blanc", "Bourgogne", BGN, B, 2020, 38, 58, "75cl"),
    ("Domaine Faiveley", "Gevrey-Chambertin", "Gevrey-Chambertin", BGN, R, 2019, 48, 72, "75cl"),
    (
        "Domaine Faiveley",
        "Mercurey 1er Cru Clos des Myglands",
        "Mercurey",
        BGN,
        R,
        2019,
        35,
        54,
        "75cl",
    ),
    (
        "Domaine Armand Rousseau",
        "Chambertin Grand Cru",
        "Chambertin",
        BGN,
        R,
        2016,
        420,
        590,
        "75cl",
    ),
    (
        "Domaine Bruno Clair",
        "Savigny-lès-Beaune",
        "Savigny-lès-Beaune",
        BGN,
        R,
        2019,
        32,
        49,
        "75cl",
    ),
    (
        "Domaine Tollot-Beaut",
        "Chorey-lès-Beaune",
        "Chorey-lès-Beaune",
        BGN,
        R,
        2020,
        22,
        35,
        "75cl",
    ),
    (
        "Domaine Louis Latour",
        "Corton-Charlemagne Grand Cru",
        "Corton-Charlemagne",
        BGN,
        B,
        2018,
        95,
        140,
        "75cl",
    ),
    (
        "Domaine Vincent Dauvissat",
        "Chablis 1er Cru La Forest",
        "Chablis",
        BGN,
        B,
        2020,
        42,
        65,
        "75cl",
    ),
    (
        "Domaine William Fèvre",
        "Chablis Grand Cru Les Clos",
        "Chablis",
        BGN,
        B,
        2019,
        68,
        99,
        "75cl",
    ),
    (
        "Domaine Maroslavac-Léger",
        "Saint-Aubin 1er Cru En Remilly",
        "Saint-Aubin",
        BGN,
        B,
        2020,
        36,
        55,
        "75cl",
    ),
    ("Domaine des Rochettes", "Pouilly-Fuissé", "Pouilly-Fuissé", BGN, B, 2021, 21, 33, "75cl"),
    ("E. Guigal", "Côte-Rôtie Brune et Blonde", "Côte-Rôtie", RHO, R, 2018, 48, 72, "75cl"),
    ("E. Guigal", "Hermitage", "Hermitage", RHO, R, 2017, 75, 112, "75cl"),
    ("Paul Jaboulet Aîné", "Hermitage La Chapelle", "Hermitage", RHO, R, 2016, 280, 380, "75cl"),
    (
        "Domaine du Vieux Télégraphe",
        "Châteauneuf-du-Pape",
        "Châteauneuf-du-Pape",
        RHO,
        R,
        2019,
        38,
        59,
        "75cl",
    ),
    (
        "Château de Beaucastel",
        "Châteauneuf-du-Pape",
        "Châteauneuf-du-Pape",
        RHO,
        R,
        2018,
        58,
        89,
        "75cl",
    ),
    (
        "Château de Beaucastel",
        "Châteauneuf-du-Pape Blanc",
        "Châteauneuf-du-Pape",
        RHO,
        B,
        2020,
        52,
        80,
        "75cl",
    ),
    ("Domaine Jamet", "Condrieu", "Condrieu", RHO, B, 2020, 55, 82, "75cl"),
    ("Domaine Clape", "Cornas", "Cornas", RHO, R, 2018, 68, 99, "75cl"),
    (
        "M. Chapoutier",
        "Crozes-Hermitage Les Meysonniers",
        "Crozes-Hermitage",
        RHO,
        R,
        2020,
        14,
        23,
        "75cl",
    ),
    ("Domaine de la Mordorée", "Tavel", "Tavel", RHO, RO, 2022, 13, 21, "75cl"),
    (
        "Domaine Didier Dagueneau",
        "Pouilly-Fumé Silex",
        "Pouilly-Fumé",
        LOI,
        B,
        2019,
        52,
        78,
        "75cl",
    ),
    (
        "Domaine Henri Bourgeois",
        "Sancerre Les Monts Damnés",
        "Sancerre",
        LOI,
        B,
        2021,
        19,
        31,
        "75cl",
    ),
    ("Domaine Vacheron", "Sancerre Rouge", "Sancerre", LOI, R, 2020, 24, 38, "75cl"),
    ("Domaine Huet", "Vouvray Le Haut-Lieu Sec", "Vouvray", LOI, B, 2020, 22, 35, "75cl"),
    (
        "Domaine Baumard",
        "Savennières Clos du Papillon",
        "Savennières",
        LOI,
        B,
        2019,
        26,
        41,
        "75cl",
    ),
    ("Domaine Bernard Baudry", "Chinon Les Granges", "Chinon", LOI, R, 2021, 12, 19, "75cl"),
    (
        "Domaine de la Pépière",
        "Muscadet Sèvre-et-Maine Clos des Briords",
        "Muscadet",
        LOI,
        B,
        2020,
        11,
        18,
        "75cl",
    ),
    ("Champagne Bollinger", "Special Cuvée Brut", "Champagne", CHA, E, None, 32, 49, "75cl"),
    ("Champagne Bollinger", "La Grande Année", "Champagne", CHA, E, 2014, 105, 155, "75cl"),
    ("Champagne Ruinart", "Blanc de Blancs", "Champagne", CHA, E, None, 48, 72, "75cl"),
    ("Champagne Taittinger", "Brut Réserve", "Champagne", CHA, E, None, 28, 44, "Magnum"),
    ("Champagne Billecart-Salmon", "Brut Rosé", "Champagne", CHA, E, None, 52, 78, "75cl"),
    ("Champagne Krug", "Grande Cuvée", "Champagne", CHA, E, None, 140, 205, "75cl"),
    (
        "Domaine Marcel Deiss",
        "Alsace Grand Cru Altenberg",
        "Alsace Grand Cru",
        ALS,
        B,
        2018,
        38,
        58,
        "75cl",
    ),
    ("Domaine Trimbach", "Riesling Cuvée Frédéric Émile", "Alsace", ALS, B, 2017, 36, 55, "75cl"),
    ("Domaine Zind-Humbrecht", "Gewurztraminer Heimbourg", "Alsace", ALS, B, 2019, 33, 50, "75cl"),
    (
        "Mas de Daumas Gassac",
        "Mas de Daumas Gassac Rouge",
        "Saint-Guilhem-le-Désert",
        LAN,
        R,
        2019,
        28,
        44,
        "75cl",
    ),
    ("Domaine Gauby", "Les Calcinaires", "Côtes du Roussillon", LAN, R, 2020, 20, 32, "75cl"),
    ("Château Simone", "Palette Rosé", "Palette", PRO, RO, 2021, 28, 44, "75cl"),
    ("Domaine Tempier", "Bandol Rouge", "Bandol", PRO, R, 2019, 30, 46, "75cl"),
    ("Château Montus", "Madiran Montus", "Madiran", SUO, R, 2018, 24, 38, "75cl"),
    ("Domaine Marcel Lapierre", "Morgon", "Morgon", BEA, R, 2021, 17, 27, "75cl"),
]

USERS = [
    ("admin@cave.fr", "admin1234", Role.admin),
    ("gestionnaire@cave.fr", "gestion1234", Role.gestionnaire),
    ("lecture@cave.fr", "lecture1234", Role.lecture_seule),
]
MOIS = 6
GRAINE = 42


def _reference(i: int, domaine: str, millesime: int | None) -> str:
    return f"{domaine.split()[-1][:4].upper()}-{millesime or 'NM'}-{i:03d}"


def creer_utilisateurs(db: Session) -> dict[Role, User]:
    users = {}
    for email, mdp, role in USERS:
        user = User(email=email, password_hash=hash_password(mdp), role=role)
        db.add(user)
        users[role] = user
    db.flush()
    return users


def creer_produits(db: Session, rng: random.Random) -> list[Product]:
    produits = []
    for i, (dom, nom, app, reg, coul, mil, achat, vente, fmt) in enumerate(VINS, start=1):
        seuil = 3 if achat > 150 else rng.choice([6, 8, 10, 12])
        produits.append(
            Product(
                reference=_reference(i, dom, mil),
                nom=nom,
                domaine=dom,
                appellation=app,
                region=reg,
                couleur=coul,
                millesime=mil,
                prix_achat=achat,
                prix_vente=vente,
                format=fmt,
                seuil_alerte=seuil,
            )
        )
    db.add_all(produits)
    db.flush()
    return produits


def creer_mouvements(
    db: Session, produits: list[Product], users: dict[Role, User], anchor: date, rng: random.Random
) -> int:
    """Simule 6 mois jour par jour, produit par produit, sans jamais passer sous zéro."""
    debut = anchor - timedelta(days=30 * MOIS)
    gestionnaire = users[Role.gestionnaire]
    n = 0

    def ajouter(p, type_, q, jour, motif):
        nonlocal n
        heure = datetime.combine(jour, datetime.min.time()) + timedelta(
            hours=rng.randint(9, 18), minutes=rng.randint(0, 59)
        )
        db.add(
            StockMovement(
                product_id=p.id,
                type=type_,
                quantite=q,
                date=heure,
                motif=motif,
                user_id=gestionnaire.id,
            )
        )
        n += 1

    for p in produits:
        cher = p.prix_achat > 150
        stock = rng.randint(3, 8) if cher else rng.randint(40, 110)
        ajouter(p, TypeMouvement.entree, stock, debut, "Stock initial")
        # Une partie des vins est volontairement écoulée vite (génère des alertes de stock).
        rythme = rng.choice([0.04, 0.06, 0.08, 0.14, 0.2]) * (0.3 if cher else 1)
        reappro = rng.random() < 0.5
        for j in range(1, (anchor - debut).days + 1):
            jour = debut + timedelta(days=j)
            if rng.random() < rythme and stock > 0:
                q = min(stock, rng.randint(1, 1 if cher else 6))
                stock -= q
                ajouter(
                    p,
                    TypeMouvement.sortie,
                    q,
                    jour,
                    rng.choice(["Vente comptoir", "Commande client", "Vente en ligne"]),
                )
            if reappro and stock <= p.seuil_alerte and rng.random() < 0.08:
                q = rng.randint(12, 36)
                stock += q
                ajouter(p, TypeMouvement.entree, q, jour, "Réapprovisionnement fournisseur")
        if rng.random() < 0.1 and stock > 1:  # inventaire : une bouteille cassée / manquante
            stock -= 1
            ajouter(
                p,
                TypeMouvement.ajustement,
                -1,
                anchor - timedelta(days=rng.randint(5, 40)),
                "Inventaire : bouteille cassée",
            )
    return n


def seed(db: Session, anchor: date, reset: bool = False) -> dict[str, int]:
    if db.scalar(select(Product.id).limit(1)):
        if not reset:
            raise SystemExit("La base contient déjà des données. Relancez avec --reset.")
        db.execute(delete(StockMovement))
        db.execute(delete(Product))
        db.execute(delete(User))
        db.commit()
    rng = random.Random(GRAINE)
    users = creer_utilisateurs(db)
    produits = creer_produits(db, rng)
    n = creer_mouvements(db, produits, users, anchor, rng)
    db.commit()
    return {"produits": len(produits), "utilisateurs": len(users), "mouvements": n}


def main() -> None:
    parser = argparse.ArgumentParser(description="Données de démonstration")
    parser.add_argument("--reset", action="store_true", help="vide les tables avant de semer")
    parser.add_argument(
        "--anchor",
        type=date.fromisoformat,
        default=date.today(),
        help="date de référence (défaut : aujourd'hui)",
    )
    args = parser.parse_args()
    with SessionLocal() as db:
        stats = seed(db, args.anchor, args.reset)
    print(f"Données créées : {stats}")
    print("Comptes (démo) : " + ", ".join(f"{e} / {m}" for e, m, _ in USERS))


if __name__ == "__main__":
    main()
