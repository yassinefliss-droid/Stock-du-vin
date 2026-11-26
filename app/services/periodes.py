from datetime import date, timedelta
from typing import Literal, get_args

Periode = Literal[
    "aujourd_hui",
    "hier",
    "cette_semaine",
    "semaine_derniere",
    "ce_mois",
    "mois_dernier",
    "7_derniers_jours",
    "30_derniers_jours",
    "6_derniers_mois",
]
PERIODES = get_args(Periode)


def resoudre_periode(nom: str, aujourdhui: date) -> tuple[date, date]:
    """Retourne (début, fin) inclusifs. Les semaines vont du lundi au dimanche."""
    lundi = aujourdhui - timedelta(days=aujourdhui.weekday())
    premier_du_mois = aujourdhui.replace(day=1)
    dernier_du_mois_prec = premier_du_mois - timedelta(days=1)
    table = {
        "aujourd_hui": (aujourdhui, aujourdhui),
        "hier": (aujourdhui - timedelta(days=1),) * 2,
        "cette_semaine": (lundi, aujourdhui),
        "semaine_derniere": (lundi - timedelta(days=7), lundi - timedelta(days=1)),
        "ce_mois": (premier_du_mois, aujourdhui),
        "mois_dernier": (dernier_du_mois_prec.replace(day=1), dernier_du_mois_prec),
        "7_derniers_jours": (aujourdhui - timedelta(days=6), aujourdhui),
        "30_derniers_jours": (aujourdhui - timedelta(days=29), aujourdhui),
        "6_derniers_mois": (aujourdhui - timedelta(days=182), aujourdhui),
    }
    if nom not in table:
        raise ValueError(f"Période inconnue : {nom}")
    return table[nom]
