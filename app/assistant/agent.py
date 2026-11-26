"""Point d'entrée de l'assistant : choisit le mode (LLM ou règles) et trace les outils appelés."""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.assistant import formatage, llm, rules, tools
from app.config import settings


@dataclass
class Reponse:
    texte: str
    mode: str  # « anthropic », « groq » ou « regles »
    outils: list[dict] = field(default_factory=list)  # [{"nom":…, "arguments":…}]


def _cle_disponible() -> bool:
    cle = {"anthropic": settings.anthropic_api_key, "groq": settings.groq_api_key}
    return bool(cle.get(settings.llm_provider))


def _repondre_regles(db: Session, question: str, note: str = "") -> Reponse:
    choix = rules.choisir_outil(db, question)
    if isinstance(choix, str):  # clarification ou hors périmètre
        return Reponse(note + choix, "regles")
    nom, args = choix
    resultat = tools.executer(db, nom, args)
    return Reponse(
        note + formatage.formater(nom, resultat), "regles", [{"nom": nom, "arguments": args}]
    )


def repondre(db: Session, question: str) -> Reponse:
    if settings.llm_provider == "none" or not _cle_disponible():
        return _repondre_regles(db, question)

    appels: list[dict] = []

    def executeur(nom: str, arguments: dict) -> dict:
        appels.append({"nom": nom, "arguments": arguments})
        return tools.executer(db, nom, arguments)

    try:
        texte = llm.repondre_avec_llm(question, str(tools.aujourdhui()), tools.OUTILS, executeur)
    except Exception as e:  # réseau, quota, clé invalide… : on dégrade en mode règles
        note = f"(LLM indisponible : {type(e).__name__} ; réponse en mode règles)\n"
        return _repondre_regles(db, question, note)
    return Reponse(texte, settings.llm_provider, appels)
