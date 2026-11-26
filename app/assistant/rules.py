"""Mode « règles » (LLM_PROVIDER=none) : mots-clés → mêmes outils que le mode LLM.

Moins souple qu'un LLM, mais gratuit, déterministe et sans clé API.
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Couleur, Product
from app.services.periodes import PERIODES
from app.services.texte import normaliser

MOTS_VIDES = set(
    "a au aux avec ce ces cette combien dans de des du en et est il ils je la le les leur "
    "mais mes mon nos notre nous on ou par pas plus pour que quel quelle quelles quels qui "
    "reste restent restant sur un une vos votre y bouteille bouteilles vin vins stock stocks "
    "valeur valent vaut total tous toutes tout cave sortie sorties entree entrees mouvement "
    "mouvements semaine derniere derniers dernier dernieres mois jours jour hier aujourd hui "
    "ce cet seuil alerte alertes rouge rouges blanc blancs rose roses effervescent effervescents "
    "euros euro prix achat vente combien quelle liste donne moi montre afficher voir sont ont "
    "ete vendu vendus vendue vendues sous ma l d s n qu vendre".split()
)

COULEURS = {
    "rouge": Couleur.rouge,
    "rouges": Couleur.rouge,
    "blanc": Couleur.blanc,
    "blancs": Couleur.blanc,
    "rose": Couleur.rose,
    "roses": Couleur.rose,
    "effervescent": Couleur.effervescent,
    "effervescents": Couleur.effervescent,
    "bulles": Couleur.effervescent,
    "petillant": Couleur.effervescent,
}

PERIODES_MOTS = [  # ordre important : le plus spécifique d'abord
    ("semaine derniere", "semaine_derniere"),
    ("semaine passee", "semaine_derniere"),
    ("cette semaine", "cette_semaine"),
    ("mois dernier", "mois_dernier"),
    ("mois passe", "mois_dernier"),
    ("ce mois", "ce_mois"),
    ("7 derniers jours", "7_derniers_jours"),
    ("30 derniers jours", "30_derniers_jours"),
    ("6 derniers mois", "6_derniers_mois"),
    ("six derniers mois", "6_derniers_mois"),
    ("hier", "hier"),
    ("aujourd hui", "aujourd_hui"),
]
assert all(p in PERIODES for _, p in PERIODES_MOTS)

AIDE = (
    "Je peux répondre sur le stock : stock d'un vin (« Combien de bouteilles de Saint-Émilion 2018 ? »), "
    "vins sous le seuil d'alerte, valeur du stock (par couleur…), mouvements d'une période "
    "(« sorties de la semaine dernière ») ou historique d'un vin."
)


def _contient(n: str, *mots: str) -> bool:
    return any(re.search(rf"\b{m}", n) for m in mots)


def _produit_cite(db: Session, n: str) -> str | None:
    """Plus longue suite de mots de la question qui figure dans le texte d'un produit."""
    textes = [f" {t} " for t in db.scalars(select(Product.search_text))]
    mots = n.split()

    def utile(m: str) -> bool:
        return m not in MOTS_VIDES and not re.fullmatch(r"(19|20)\d\d", m)

    for taille in range(min(4, len(mots)), 0, -1):
        for i in range(len(mots) - taille + 1):
            fenetre = mots[i : i + taille]
            if not (utile(fenetre[0]) and utile(fenetre[-1])):
                continue
            phrase = f" {' '.join(fenetre)} "
            if any(phrase in t for t in textes):
                return " ".join(fenetre)
    return None


def choisir_outil(db: Session, question: str) -> tuple[str, dict] | str:
    """Retourne (nom_outil, arguments) ou un message (clarification / hors périmètre)."""
    n = normaliser(question)
    couleur = next((c.value for mot, c in COULEURS.items() if re.search(rf"\b{mot}\b", n)), None)
    annee = re.search(r"\b((?:19|20)\d\d)\b", n)
    millesime = int(annee.group(1)) if annee else None
    periode = next((p for mot, p in PERIODES_MOTS if mot in n), None)
    produit = _produit_cite(db, n)

    def filtres(**extra) -> dict:
        args = {"couleur": couleur, "millesime": millesime, "recherche": produit, **extra}
        return {k: v for k, v in args.items() if v is not None}

    if _contient(n, "seuil", "alerte", "rupture", "reappro", "manque", "epuis"):
        args = filtres()
        args.pop("millesime", None)
        return "produits_sous_seuil", args

    if _contient(n, "historique", "dernier mouvement", "derniers mouvements") and produit:
        return "historique_produit", {
            "recherche": produit,
            **({"millesime": millesime} if millesime else {}),
        }

    # « valeur / prix » avant « mouvements » : sinon « prix de vente » serait pris pour des ventes.
    if _contient(n, "valeur", "vaut", "valent", "euro", "prix"):
        return "resume_stock", filtres()

    if _contient(n, "sortie", "entree", "mouvement", "vendu", "vente", "livraison", "recu"):
        args = filtres(periode=periode or "30_derniers_jours")
        args.pop("millesime", None)
        if _contient(n, "sortie", "vendu", "vente"):
            args["type"] = "sortie"
        elif _contient(n, "entree", "livraison", "recu"):
            args["type"] = "entree"
        return "mouvements_periode", args

    if _contient(n, "total", "au global", "en tout"):
        return "resume_stock", filtres()

    if _contient(n, "combien", "reste", "stock", "bouteille", "en cave", "disponible"):
        if produit:
            return "stock_produit", filtres()
        if couleur or millesime:
            return "resume_stock", filtres()
        return (
            "Pouvez-vous préciser de quel vin il s'agit (appellation, domaine, cuvée…) "
            "ou donner un filtre (couleur, millésime) ? Pour le stock global, "
            "demandez « stock total »."
        )

    return AIDE
