"""Évalue l'assistant sur eval/questions.yaml.

    python -m eval.run_eval [--provider none|anthropic|groq]

Deux métriques : bon outil choisi, et réponse correcte (tous les chiffres/textes attendus
présents ; pour les questions sans outil attendu : aucun outil appelé).
"""

import argparse
import re
from pathlib import Path

import yaml

from app.assistant import agent
from app.config import settings
from app.services.texte import normaliser
from eval.common import ANCHOR, base_eval


def nombres_presents(texte: str, attendu: str) -> bool:
    # « 12 345,67 » / « 12 345 » → « 12345,67 » ; l'attendu ne doit pas être un morceau d'un autre nombre.
    texte = re.sub(r"(?<=\d)[\s  ](?=\d)", "", texte)
    return re.search(rf"(?<![\d]){re.escape(attendu)}(?![\d])", texte) is not None


def evaluer(question: dict, reponse: agent.Reponse) -> tuple[bool, bool]:
    appeles = [o["nom"] for o in reponse.outils]
    attendu = question["outil_attendu"]
    bon_outil = (appeles[:1] == [attendu]) if attendu else not appeles
    if attendu is None:
        return bon_outil, bon_outil  # correct = a bien refusé / demandé une précision
    ok = all(nombres_presents(reponse.texte, c) for c in question["chiffres"]) and all(
        normaliser(t) in normaliser(reponse.texte) for t in question["textes"]
    )
    return bon_outil, ok and bon_outil


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["none", "anthropic", "groq"])
    args = parser.parse_args()
    if args.provider:
        settings.llm_provider = args.provider

    questions = yaml.safe_load((Path(__file__).parent / "questions.yaml").read_text())
    settings.assistant_today = ANCHOR
    db = base_eval()
    mode = settings.llm_provider if agent._cle_disponible() else "regles"
    if settings.llm_provider != "none" and mode == "regles":
        print(f"⚠ Pas de clé API pour {settings.llm_provider} : évaluation en mode règles.\n")

    n_outil = n_ok = 0
    modes: dict[str, int] = {}
    for i, q in enumerate(questions, start=1):
        r = agent.repondre(db, q["question"])
        bon_outil, correct = evaluer(q, r)
        modes[r.mode] = modes.get(r.mode, 0) + 1
        n_outil += bon_outil
        n_ok += correct
        appeles = ",".join(o["nom"] for o in r.outils) or "aucun"
        print(f"{i:2d}. [{'OK' if bon_outil else 'KO'} outil | {'OK' if correct else 'KO'} réponse] "
              f"{q['question']} ({r.mode})")  # fmt: skip
        print(f"      attendu: {q['outil_attendu'] or 'aucun'} {q['chiffres'] or q['textes'] or ''}"
              f" | obtenu: {appeles}")  # fmt: skip
        if not correct:
            print("      réponse:", r.texte.replace("\n", " ")[:200])
    n = len(questions)
    # Mode RÉEL de chaque réponse : un appel LLM en échec retombe silencieusement en « regles ».
    print(f"\nMode demandé : {mode}  |  modes réellement utilisés : {modes}  |  ancre : {ANCHOR}")
    if settings.llm_provider != "none" and modes.get("regles"):
        print(
            f"⚠ {modes['regles']} réponse(s) en repli mode règles (LLM indisponible) : "
            "ces résultats ne mesurent PAS le LLM."
        )
    print(f"Bon outil choisi : {n_outil}/{n} ({100 * n_outil / n:.0f} %)")
    print(f"Réponses correctes : {n_ok}/{n} ({100 * n_ok / n:.0f} %)")


if __name__ == "__main__":
    main()
