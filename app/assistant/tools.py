"""Outils de l'assistant : fonctions Python déterministes, en LECTURE SEULE.

Le LLM (ou le mode règles) ne fait que CHOISIR un outil et ses paramètres ;
tous les chiffres viennent de ces fonctions, jamais du modèle.
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Couleur, TypeMouvement
from app.services import stock as svc
from app.services.periodes import Periode, resoudre_periode


def aujourdhui() -> date:
    return settings.assistant_today or date.today()


# --- Paramètres (le schéma JSON envoyé au LLM est généré depuis ces modèles) -------------


COULEUR_DESC = "rouge, blanc, rose ou effervescent (exactement, en minuscules)"


class ParamsStockProduit(BaseModel):
    recherche: str = Field(
        description="Mots du produit : appellation, domaine, nom ou région (ex. « Saint-Émilion »)"
    )
    millesime: int | None = Field(default=None, description="Année du millésime, ex. 2018")
    couleur: Couleur | None = Field(default=None, description=COULEUR_DESC)


class ParamsSousSeuil(BaseModel):
    couleur: Couleur | None = Field(default=None, description=COULEUR_DESC)
    recherche: str | None = Field(
        default=None, description="Filtre optionnel (région, appellation…)"
    )


class ParamsResume(BaseModel):
    couleur: Couleur | None = Field(default=None, description=COULEUR_DESC)
    recherche: str | None = Field(
        default=None, description="Filtre optionnel (région, appellation…)"
    )
    millesime: int | None = None


class ParamsMouvements(BaseModel):
    type: Literal["entree", "sortie", "ajustement"] | None = Field(
        default=None, description="Type de mouvement ; vide = tous"
    )
    periode: Periode | None = Field(default=None, description="Période nommée")
    debut: date | None = Field(default=None, description="Début AAAA-MM-JJ (si pas de période)")
    fin: date | None = Field(default=None, description="Fin AAAA-MM-JJ (si pas de période)")
    recherche: str | None = Field(default=None, description="Filtre optionnel sur le produit")
    couleur: Couleur | None = Field(default=None, description=COULEUR_DESC)


class ParamsHistorique(BaseModel):
    recherche: str = Field(description="Produit concerné (nom, domaine, appellation…)")
    millesime: int | None = None
    limite: int = Field(default=10, ge=1, le=30)


# --- Fonctions ---------------------------------------------------------------------------


def _produit_dict(x: svc.ProduitStock) -> dict[str, Any]:
    p = x.produit
    return {
        "reference": p.reference,
        "nom": p.nom,
        "millesime": p.millesime,
        "format": p.format,
        "couleur": p.couleur.value,
        "stock": x.stock,
        "seuil_alerte": p.seuil_alerte,
    }


def stock_produit(db: Session, p: ParamsStockProduit) -> dict:
    lignes = svc.lister(db, svc.Filtre(p.recherche, p.couleur, p.millesime))
    return {
        "nombre_produits": len(lignes),
        "total_bouteilles": sum(x.stock for x in lignes),
        "produits": [_produit_dict(x) for x in lignes[:20]],
    }


def produits_sous_seuil(db: Session, p: ParamsSousSeuil) -> dict:
    lignes = svc.lister(db, svc.Filtre(p.recherche, p.couleur), sous_seuil=True)
    return {"nombre_produits": len(lignes), "produits": [_produit_dict(x) for x in lignes[:30]]}


def resume_stock(db: Session, p: ParamsResume) -> dict:
    v = svc.valeur(svc.lister(db, svc.Filtre(p.recherche, p.couleur, p.millesime)))
    return {
        "nombre_references": v.references,
        "total_bouteilles": v.bouteilles,
        "valeur_achat_eur": float(v.valeur_achat),
        "valeur_vente_eur": float(v.valeur_vente),
    }


def mouvements_periode(db: Session, p: ParamsMouvements) -> dict:
    if p.periode:
        debut, fin = resoudre_periode(p.periode, aujourdhui())
    elif p.debut or p.fin:
        debut, fin = p.debut, p.fin
    else:
        debut, fin = resoudre_periode("30_derniers_jours", aujourdhui())
    mouvements = svc.historique(
        db,
        filtre=svc.Filtre(p.recherche, p.couleur),
        debut=debut,
        fin=fin,
        type=TypeMouvement(p.type) if p.type else None,
        limite=None,
    )
    par_type: dict[str, int] = defaultdict(int)
    par_produit: dict[str, int] = defaultdict(int)
    for m in mouvements:
        par_type[m.type.value] += m.quantite
        par_produit[f"{m.product.nom} {m.product.millesime or ''}".strip()] += abs(m.quantite)
    top = sorted(par_produit.items(), key=lambda kv: -kv[1])[:10]
    return {
        "debut": str(debut) if debut else None,
        "fin": str(fin) if fin else None,
        "nombre_mouvements": len(mouvements),
        "quantite_par_type": dict(par_type),
        "produits_les_plus_concernes": [{"nom": n, "quantite": q} for n, q in top],
    }


def historique_produit(db: Session, p: ParamsHistorique) -> dict:
    mouvements = svc.historique(
        db, filtre=svc.Filtre(p.recherche, millesime=p.millesime), limite=p.limite
    )
    return {
        "mouvements": [
            {
                "date": m.date.strftime("%Y-%m-%d"),
                "produit": m.product.nom,
                "millesime": m.product.millesime,
                "type": m.type.value,
                "quantite": m.quantite,
                "motif": m.motif,
            }
            for m in mouvements
        ]
    }


# --- Registre ----------------------------------------------------------------------------


@dataclass
class Outil:
    nom: str
    description: str
    params: type[BaseModel]
    fonction: Callable[[Session, Any], dict]


OUTILS: dict[str, Outil] = {
    o.nom: o
    for o in [
        Outil(
            "stock_produit",
            "Stock actuel (nombre de bouteilles) d'un vin ou d'un groupe de vins précis : "
            "une appellation, un domaine, une cuvée, éventuellement un millésime.",
            ParamsStockProduit,
            stock_produit,
        ),
        Outil(
            "produits_sous_seuil",
            "Liste les vins dont le stock a atteint ou franchi le seuil d'alerte (à réapprovisionner).",
            ParamsSousSeuil,
            produits_sous_seuil,
        ),
        Outil(
            "resume_stock",
            "Résumé global du stock : total de bouteilles, valeur au prix d'achat et de vente, "
            "pour toute la cave ou filtré par couleur / région / appellation / millésime.",
            ParamsResume,
            resume_stock,
        ),
        Outil(
            "mouvements_periode",
            "Totaux des mouvements (entrées, sorties, ajustements) sur une période, "
            "avec les produits les plus concernés.",
            ParamsMouvements,
            mouvements_periode,
        ),
        Outil(
            "historique_produit",
            "Derniers mouvements de stock d'un vin donné.",
            ParamsHistorique,
            historique_produit,
        ),
    ]
}


def executer(db: Session, nom: str, arguments: dict) -> dict:
    """Valide les arguments puis exécute l'outil. Les erreurs sont renvoyées (pas levées) pour
    que le LLM puisse corriger ou demander une précision."""
    outil = OUTILS.get(nom)
    if outil is None:
        return {"erreur": f"Outil inconnu : {nom}"}
    try:
        params = outil.params(**arguments)
    except ValidationError as e:
        return {"erreur": f"Paramètres invalides : {e.errors(include_url=False)}"}
    return outil.fonction(db, params)
