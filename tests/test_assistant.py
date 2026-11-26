"""Un test par outil + le routage du mode règles + le comportement de l'agent (LLM simulé)."""

import pytest

from app.assistant import agent, llm, tools
from app.config import settings
from app.models import Role
from app.services.periodes import resoudre_periode
from tests.conftest import AUJOURDHUI


def run(db, nom, **args):
    return tools.executer(db, nom, args)


# --- Outils --------------------------------------------------------------------------------


def test_outil_stock_produit(db, cave):
    r = run(db, "stock_produit", recherche="Saint-Émilion", millesime=2018)
    assert r["total_bouteilles"] == 20  # Figeac 17 + Angélus 3
    assert {p["reference"] for p in r["produits"]} == {"FIG-18", "ANG-18"}


def test_outil_stock_produit_inconnu(db, cave):
    assert run(db, "stock_produit", recherche="Pomerol")["nombre_produits"] == 0


def test_outil_produits_sous_seuil(db, cave):
    r = run(db, "produits_sous_seuil")
    assert {p["reference"]: p["stock"] for p in r["produits"]} == {"ANG-18": 3, "KRU-NM": 4}
    assert run(db, "produits_sous_seuil", couleur="rouge")["nombre_produits"] == 1


def test_outil_resume_stock(db, cave):
    r = run(db, "resume_stock", couleur="blanc")
    assert (r["total_bouteilles"], r["valeur_achat_eur"], r["valeur_vente_eur"]) == (10, 400, 600)
    assert run(db, "resume_stock")["total_bouteilles"] == 34


def test_outil_mouvements_semaine_derniere(db, cave):
    # semaine du lun. 9 au dim. 15 juin : sortie Figeac (12/06) et sortie Krug (11/06)
    r = run(db, "mouvements_periode", type="sortie", periode="semaine_derniere")
    assert (r["debut"], r["fin"]) == ("2025-06-09", "2025-06-15")
    assert r["quantite_par_type"] == {"sortie": 7}
    assert r["produits_les_plus_concernes"][0] == {"nom": "Château Figeac 2018", "quantite": 5}


def test_outil_mouvements_dates_explicites_et_tous_types(db, cave):
    r = run(db, "mouvements_periode", debut="2025-06-16", fin="2025-06-17")
    assert r["nombre_mouvements"] == 2
    assert r["quantite_par_type"] == {"ajustement": 2, "sortie": 1}


def test_outil_historique_produit(db, cave):
    r = run(db, "historique_produit", recherche="Angélus", limite=5)
    assert [m["type"] for m in r["mouvements"]] == ["sortie", "entree"]


def test_outil_arguments_invalides_ou_inconnus(db, cave):
    assert "erreur" in run(db, "stock_produit")  # paramètre obligatoire manquant
    assert "erreur" in run(db, "mouvements_periode", periode="l_an_dernier")
    assert "erreur" in run(db, "supprimer_tout")


def test_periodes():
    assert resoudre_periode("hier", AUJOURDHUI)[0].isoformat() == "2025-06-17"
    assert resoudre_periode("cette_semaine", AUJOURDHUI)[0].isoformat() == "2025-06-16"
    assert resoudre_periode("mois_dernier", AUJOURDHUI) == (
        AUJOURDHUI.replace(month=5, day=1),
        AUJOURDHUI.replace(month=5, day=31),
    )


def test_schemas_d_outils_sont_generes_pour_le_llm():
    schema = tools.OUTILS["mouvements_periode"].params.model_json_schema()
    assert "periode" in schema["properties"]
    assert all(o.description for o in tools.OUTILS.values())


# --- Mode règles ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "question, outil",
    [
        ("Combien de bouteilles de Saint-Émilion 2018 reste-t-il ?", "stock_produit"),
        ("Quels vins sont sous le seuil d'alerte ?", "produits_sous_seuil"),
        ("Quelle est la valeur du stock de blancs ?", "resume_stock"),
        ("Quelles ont été les sorties de la semaine dernière ?", "mouvements_periode"),
        ("Historique de Château Figeac", "historique_produit"),
        ("Quel est le stock total ?", "resume_stock"),
        ("Valeur du stock de Bordeaux au prix de vente ?", "resume_stock"),  # « vente » ≠ sorties
        ("Quel est le total des entrées du mois dernier ?", "mouvements_periode"),
    ],
)
def test_regles_choisissent_le_bon_outil(db, cave, question, outil):
    r = agent.repondre(db, question)
    assert r.mode == "regles"
    assert [o["nom"] for o in r.outils] == [outil]


def test_regles_reponse_avec_chiffres_de_l_outil(db, cave):
    r = agent.repondre(db, "Combien de bouteilles de Saint-Émilion 2018 reste-t-il ?")
    assert "20 bouteille" in r.texte and "Château Figeac" in r.texte
    r = agent.repondre(db, "Quelle est la valeur du stock de blancs ?")
    assert "400,00 €" in r.texte and "600,00 €" in r.texte


def test_regles_hors_perimetre_et_ambigu(db, cave):
    hors = agent.repondre(db, "Quelle est la capitale de la France ?")
    assert hors.outils == [] and "stock" in hors.texte
    flou = agent.repondre(db, "Combien il en reste ?")
    assert flou.outils == [] and "préciser" in flou.texte


# --- Agent LLM (le fournisseur est simulé : pas de réseau dans les tests) ---------------------


def test_agent_llm_trace_les_outils(db, cave, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "cle-factice")

    def faux_llm(question, date_jour, outils, executeur):
        resultat = executeur("resume_stock", {"couleur": "blanc"})
        return f"{resultat['total_bouteilles']} bouteilles de blanc."

    monkeypatch.setattr(llm, "repondre_avec_llm", faux_llm)
    r = agent.repondre(db, "Combien de blancs ?")
    assert r.mode == "anthropic" and r.texte == "10 bouteilles de blanc."
    assert r.outils == [{"nom": "resume_stock", "arguments": {"couleur": "blanc"}}]


def test_agent_retombe_en_regles_si_le_llm_echoue(db, cave, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "cle-factice")

    def en_panne(*args, **kwargs):
        raise ConnectionError("réseau coupé")

    monkeypatch.setattr(llm, "repondre_avec_llm", en_panne)
    r = agent.repondre(db, "Quels vins sont sous le seuil d'alerte ?")
    assert r.mode == "regles" and "LLM indisponible" in r.texte and "Angélus" in r.texte


def test_sans_cle_on_reste_en_mode_regles(db, cave, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    assert agent.repondre(db, "Quel est le stock total ?").mode == "regles"


def test_endpoint_assistant(client, cave, auth):
    corps = {"question": "Quels vins sont sous le seuil d'alerte ?"}
    assert client.post("/api/assistant/ask", json=corps).status_code == 401
    r = client.post("/api/assistant/ask", json=corps, headers=auth[Role.lecture_seule])
    assert r.status_code == 200
    assert r.json()["outils"][0]["nom"] == "produits_sous_seuil"


def test_boucle_tool_calling_groq(db, cave, monkeypatch):
    """Vérifie la boucle outil → résultat → réponse, avec une API HTTP simulée."""
    monkeypatch.setattr(settings, "llm_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "cle-factice")
    envois = []

    class Rep:
        status_code = 200
        headers: dict = {}

        def __init__(self, message):
            self.message = message

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": self.message}]}

    def faux_post(url, headers, json, timeout):
        envois.append(list(json["messages"]))
        if len(envois) == 1:  # 1er tour : le modèle demande un outil
            appel = {
                "id": "c1",
                "type": "function",
                "function": {"name": "resume_stock", "arguments": '{"couleur": "blanc"}'},
            }
            return Rep({"role": "assistant", "content": None, "tool_calls": [appel]})
        resultat = envois[-1][-1]  # 2e tour : il a reçu le résultat de l'outil
        assert resultat["role"] == "tool" and '"total_bouteilles": 10' in resultat["content"]
        return Rep({"role": "assistant", "content": "Il y a 10 bouteilles de blanc."})

    monkeypatch.setattr(llm.httpx, "post", faux_post)
    r = agent.repondre(db, "Combien de blancs ?")
    assert r.texte == "Il y a 10 bouteilles de blanc." and r.mode == "groq"
    assert r.outils[0]["nom"] == "resume_stock"


def test_boucle_tool_calling_anthropic(db, cave, monkeypatch):
    """Même vérification pour le SDK Anthropic, avec un faux client."""
    from types import SimpleNamespace as NS

    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "cle-factice")
    appels = []

    class FauxMessages:
        def create(self, **kw):
            appels.append(kw)
            assert {t["name"] for t in kw["tools"]} == set(tools.OUTILS)
            if len(appels) == 1:
                bloc = NS(type="tool_use", id="t1", name="produits_sous_seuil", input={})
                return NS(stop_reason="tool_use", content=[bloc])
            retour = kw["messages"][-1]["content"][0]
            assert retour["type"] == "tool_result" and "Angélus" in retour["content"]
            return NS(
                stop_reason="end_turn", content=[NS(type="text", text="2 vins à recommander.")]
            )

    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", lambda api_key: NS(messages=FauxMessages()))
    r = agent.repondre(db, "Que faut-il recommander ?")
    assert r.texte == "2 vins à recommander." and r.outils[0]["nom"] == "produits_sous_seuil"
