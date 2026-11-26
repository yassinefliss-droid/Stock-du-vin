"""Boucle de tool calling avec Anthropic ou Groq (API compatible OpenAI).

Le modèle reçoit la liste des outils ; quand il en demande un, on l'exécute côté serveur
(lecture seule) et on lui renvoie le résultat JSON, puis il rédige la réponse.
"""

import json
import time
from collections.abc import Callable

import httpx

from app.config import settings

MODELES_PAR_DEFAUT = {"anthropic": "claude-haiku-5-5", "groq": "openai/gpt-oss-120b"}
MAX_TOURS = 4

SYSTEME = """Tu es l'assistant de stock d'une cave à vins. Tu réponds en français, de façon brève.
Règles strictes :
- Pour toute donnée chiffrée (stock, valeur, mouvements), tu DOIS appeler un outil. Tu n'as accès à aucune autre donnée.
- Tu n'inventes jamais un chiffre : tu cites uniquement les produits et valeurs renvoyés par l'outil.
- Pour les paramètres à valeurs fixes (couleur, type, période), utilise exactement les valeurs du schéma, en minuscules.
- Quand l'outil renvoie une liste, indique aussi le nombre total d'éléments.
- Si l'outil ne renvoie aucun résultat, dis-le simplement.
- Si la question est hors sujet (autre que le stock de la cave) ou trop ambiguë pour choisir un outil, n'appelle aucun outil : dis que c'est hors périmètre ou pose une question de précision.
- Aujourd'hui nous sommes le {date}. Les semaines vont du lundi au dimanche."""

# executeur(nom, arguments) -> dict ; appelé pour chaque demande d'outil du modèle.
Executeur = Callable[[str, dict], dict]


def _schemas(outils) -> list[dict]:
    return [
        {"name": o.nom, "description": o.description, "schema": o.params.model_json_schema()}
        for o in outils.values()
    ]


def _anthropic(question: str, systeme: str, outils, executeur: Executeur) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    modele = settings.llm_model or MODELES_PAR_DEFAUT["anthropic"]
    schemas = [
        {"name": s["name"], "description": s["description"], "input_schema": s["schema"]}
        for s in _schemas(outils)
    ]
    messages: list[dict] = [{"role": "user", "content": question}]
    for _ in range(MAX_TOURS):
        r = client.messages.create(
            model=modele, max_tokens=1024, system=systeme, tools=schemas, messages=messages
        )
        if r.stop_reason != "tool_use":
            return "".join(b.text for b in r.content if b.type == "text")
        messages.append({"role": "assistant", "content": r.content})
        resultats = [
            {
                "type": "tool_result",
                "tool_use_id": b.id,
                "content": json.dumps(executeur(b.name, b.input), ensure_ascii=False),
            }
            for b in r.content
            if b.type == "tool_use"
        ]
        messages.append({"role": "user", "content": resultats})
    return "Je n'ai pas réussi à répondre à cette question."


def _post_groq(modele: str, messages: list, schemas: list):
    """POST avec nouvel essai sur 429 (limite de débit de l'offre gratuite : tokens/minute)."""
    for essai in range(6):
        reponse = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json={"model": modele, "messages": messages, "tools": schemas, "temperature": 0},
            timeout=60,
        )
        if reponse.status_code != 429 or essai == 5:
            reponse.raise_for_status()
            return reponse
        time.sleep(min(float(reponse.headers.get("retry-after", 5)) + 1, 30))


def _groq(question: str, systeme: str, outils, executeur: Executeur) -> str:
    modele = settings.llm_model or MODELES_PAR_DEFAUT["groq"]
    schemas = [
        {
            "type": "function",
            "function": {
                "name": s["name"],
                "description": s["description"],
                "parameters": s["schema"],
            },
        }
        for s in _schemas(outils)
    ]
    messages: list[dict] = [
        {"role": "system", "content": systeme},
        {"role": "user", "content": question},
    ]
    for _ in range(MAX_TOURS):
        reponse = _post_groq(modele, messages, schemas)
        message = reponse.json()["choices"][0]["message"]
        if not message.get("tool_calls"):
            return message.get("content") or ""
        messages.append(message)
        for appel in message["tool_calls"]:
            fn = appel["function"]
            resultat = executeur(fn["name"], json.loads(fn["arguments"] or "{}"))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": appel["id"],
                    "content": json.dumps(resultat, ensure_ascii=False),
                }
            )
    return "Je n'ai pas réussi à répondre à cette question."


def repondre_avec_llm(question: str, date_jour: str, outils, executeur: Executeur) -> str:
    systeme = SYSTEME.format(date=date_jour)
    if settings.llm_provider == "anthropic":
        return _anthropic(question, systeme, outils, executeur)
    if settings.llm_provider == "groq":
        return _groq(question, systeme, outils, executeur)
    raise ValueError("Aucun fournisseur LLM configuré")
