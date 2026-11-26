"""Logique de stock. Le stock n'est JAMAIS stocké : il se déduit des mouvements."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Couleur, Product, StockMovement, TypeMouvement
from app.services.erreurs import Introuvable, StockInsuffisant
from app.services.texte import normaliser

# Variation de stock d'un mouvement, en SQL : une sortie retire, le reste ajoute (signé).
DELTA = case(
    (StockMovement.type == TypeMouvement.sortie, -StockMovement.quantite),
    else_=StockMovement.quantite,
)


@dataclass
class Filtre:
    recherche: str | None = None
    couleur: Couleur | None = None
    millesime: int | None = None


@dataclass
class ProduitStock:
    produit: Product
    stock: int


@dataclass
class Valeur:
    references: int
    bouteilles: int
    valeur_achat: Decimal
    valeur_vente: Decimal


def stock_courant(db: Session, product_id: int) -> int:
    total = db.scalar(select(func.sum(DELTA)).where(StockMovement.product_id == product_id))
    return int(total or 0)


def lister(
    db: Session, filtre: Filtre | None = None, sous_seuil: bool = False
) -> list[ProduitStock]:
    """Produits avec leur stock courant, filtrés. Une seule requête (jointure sur les sommes)."""
    filtre = filtre or Filtre()
    sommes = (
        select(StockMovement.product_id.label("pid"), func.sum(DELTA).label("stock"))
        .group_by(StockMovement.product_id)
        .subquery()
    )
    stock = func.coalesce(sommes.c.stock, 0)
    requete = select(Product, stock).outerjoin(sommes, sommes.c.pid == Product.id)

    # Chaque mot de la recherche doit apparaître (sans accents) dans le texte du produit.
    for mot in normaliser(filtre.recherche or "").split():
        requete = requete.where(Product.search_text.contains(mot, autoescape=True))
    if filtre.couleur:
        requete = requete.where(Product.couleur == filtre.couleur)
    if filtre.millesime:
        requete = requete.where(Product.millesime == filtre.millesime)
    if sous_seuil:
        requete = requete.where(stock <= Product.seuil_alerte)

    requete = requete.order_by(Product.region, Product.nom, Product.millesime)
    return [ProduitStock(p, int(s)) for p, s in db.execute(requete)]


def valeur(lignes: list[ProduitStock]) -> Valeur:
    return Valeur(
        references=len(lignes),
        bouteilles=sum(x.stock for x in lignes),
        valeur_achat=sum((x.stock * x.produit.prix_achat for x in lignes), Decimal(0)),
        valeur_vente=sum((x.stock * x.produit.prix_vente for x in lignes), Decimal(0)),
    )


def enregistrer_mouvement(
    db: Session,
    *,
    product_id: int,
    type: TypeMouvement,
    quantite: int,
    date_mouvement: datetime | None = None,
    motif: str = "",
    user_id: int | None = None,
) -> StockMovement:
    """Enregistre un mouvement ; refuse tout ce qui rendrait le stock négatif."""
    # Verrou de ligne (no-op sous SQLite) : deux sorties simultanées ne peuvent pas
    # passer toutes les deux la vérification.
    produit = db.get(Product, product_id, with_for_update=True)
    if produit is None:
        raise Introuvable(f"Produit {product_id} introuvable")

    mouvement = StockMovement(
        product_id=product_id,
        type=type,
        quantite=quantite,
        date=date_mouvement or datetime.now(),
        motif=motif,
        user_id=user_id,
    )
    actuel = stock_courant(db, product_id)
    if actuel + mouvement.delta < 0:
        db.rollback()
        raise StockInsuffisant(
            f"Stock insuffisant pour « {produit.nom} » : {actuel} en stock, "
            f"mouvement de {mouvement.delta:+d} refusé"
        )
    db.add(mouvement)
    db.commit()
    return mouvement


def historique(
    db: Session,
    *,
    product_id: int | None = None,
    filtre: Filtre | None = None,
    debut: date | None = None,
    fin: date | None = None,
    type: TypeMouvement | None = None,
    limite: int | None = 200,
) -> list[StockMovement]:
    """Mouvements (récents d'abord), filtrables par produit, période (bornes incluses) et type."""
    requete = select(StockMovement).join(Product)
    if product_id is not None:
        requete = requete.where(StockMovement.product_id == product_id)
    if filtre:
        for mot in normaliser(filtre.recherche or "").split():
            requete = requete.where(Product.search_text.contains(mot, autoescape=True))
        if filtre.couleur:
            requete = requete.where(Product.couleur == filtre.couleur)
        if filtre.millesime:
            requete = requete.where(Product.millesime == filtre.millesime)
    if debut:
        requete = requete.where(StockMovement.date >= datetime.combine(debut, datetime.min.time()))
    if fin:
        requete = requete.where(
            StockMovement.date < datetime.combine(fin + timedelta(days=1), datetime.min.time())
        )
    if type:
        requete = requete.where(StockMovement.type == type)
    requete = requete.order_by(StockMovement.date.desc(), StockMovement.id.desc())
    if limite:
        requete = requete.limit(limite)
    return list(db.scalars(requete))
