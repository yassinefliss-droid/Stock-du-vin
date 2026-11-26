"""Interface Streamlit : un client de l'API REST (aucune logique métier ici).

streamlit run streamlit_app/app.py        # API attendue sur API_URL (défaut http://localhost:8000)
"""

import os
from datetime import datetime

import httpx
import pandas as pd
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")
COULEURS = ["", "rouge", "blanc", "rose", "effervescent"]

st.set_page_config(page_title="Stock en cave", page_icon="🍷", layout="wide")


def api(methode: str, chemin: str, **kw):
    """Appel authentifié ; retourne (réponse JSON ou None, message d'erreur ou None)."""
    headers = {"Authorization": f"Bearer {st.session_state.get('token', '')}"}
    try:
        r = httpx.request(methode, API_URL + chemin, headers=headers, timeout=60, **kw)
    except httpx.HTTPError as e:
        return None, f"API injoignable ({API_URL}) : {e}"
    if r.status_code == 401 and "token" in st.session_state:
        del st.session_state["token"]
        st.rerun()
    if r.is_error:
        detail = (
            r.json().get("detail", r.text)
            if r.headers.get("content-type", "").startswith("application/json")
            else r.text
        )
        return None, f"{r.status_code} — {detail}"
    return (r.json() if r.content else None), None


def eur(x) -> str:
    return f"{float(x):,.2f}".replace(",", " ").replace(".", ",") + " €"


def table(produits: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(produits)
    if df.empty:
        return df
    df["millesime"] = df["millesime"].astype("Int64")
    cols = ["id", "reference", "nom", "appellation", "region", "millesime", "couleur",
            "prix_achat", "prix_vente", "stock", "seuil_alerte"]  # fmt: skip
    return df[cols]


# --- Connexion ---------------------------------------------------------------------------


def page_connexion():
    st.title("🍷 Stock en cave")
    with st.form("login"):
        email = st.text_input("Email")
        mdp = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Se connecter"):
            try:
                r = httpx.post(
                    f"{API_URL}/api/auth/token",
                    data={"username": email, "password": mdp},
                    timeout=30,
                )
            except httpx.HTTPError as e:
                st.error(f"API injoignable ({API_URL}) : {e}")
                return
            if r.is_error:
                st.error("Email ou mot de passe incorrect")
                return
            st.session_state["token"] = r.json()["access_token"]
            st.session_state["user"], _ = api("GET", "/api/auth/me")
            st.rerun()


# --- Pages -------------------------------------------------------------------------------


def page_dashboard():
    st.title("Tableau de bord")
    v, err = api("GET", "/api/stock/valeur")
    alertes, err2 = api("GET", "/api/stock/alertes")
    if err or err2:
        return st.error(err or err2)
    c = st.columns(4)
    c[0].metric(
        "Bouteilles en stock", v["bouteilles"], f"{v['references']} références", delta_color="off"
    )
    c[1].metric("Valeur (prix d'achat)", eur(v["valeur_achat"]))
    c[2].metric("Valeur (prix de vente)", eur(v["valeur_vente"]))
    c[3].metric("Produits sous le seuil", len(alertes))
    st.subheader("Alertes de stock")
    if alertes:
        st.dataframe(table(alertes), hide_index=True, width="stretch")
    else:
        st.success("Aucune alerte.")


def page_produits():
    st.title("Produits")
    c = st.columns([3, 1, 1])
    recherche = c[0].text_input("Recherche (nom, domaine, appellation, région, millésime)")
    couleur = c[1].selectbox("Couleur", COULEURS)
    sous_seuil = c[2].checkbox("Sous le seuil")
    params = {"recherche": recherche or None, "couleur": couleur or None, "sous_seuil": sous_seuil}
    produits, err = api("GET", "/api/products", params={k: v for k, v in params.items() if v})
    if err:
        return st.error(err)
    st.caption(f"{len(produits)} produit(s)")
    st.dataframe(table(produits), hide_index=True, width="stretch")

    if not produits:
        return
    st.subheader("Fiche produit")
    choix = {f"{p['nom']} {p['millesime'] or 'NM'} — stock {p['stock']}": p for p in produits}
    p = choix[st.selectbox("Produit", list(choix))]
    st.write(f"**{p['domaine']}** · {p['appellation']} ({p['region']}) · {p['couleur']} · {p['format']}  \n"
             f"Achat {eur(p['prix_achat'])} · Vente {eur(p['prix_vente'])} · "
             f"**Stock : {p['stock']}** (seuil {p['seuil_alerte']})")  # fmt: skip
    mouvements, err = api("GET", "/api/movements", params={"product_id": p["id"], "limite": 100})
    if err:
        return st.error(err)
    st.dataframe(pd.DataFrame(mouvements), hide_index=True, width="stretch")


def page_mouvement():
    st.title("Enregistrer un mouvement")
    if st.session_state["user"]["role"] == "lecture_seule":
        return st.warning("Votre rôle est en lecture seule.")
    produits, err = api("GET", "/api/products")
    if err:
        return st.error(err)
    choix = {f"{p['nom']} {p['millesime'] or 'NM'} — stock {p['stock']}": p["id"] for p in produits}
    with st.form("mvt", clear_on_submit=True):
        produit = st.selectbox("Produit", list(choix))
        type_ = st.selectbox("Type", ["entree", "sortie", "ajustement"],
                             help="Ajustement : quantité signée (ex. -2)")  # fmt: skip
        quantite = st.number_input("Quantité", value=1, step=1)
        motif = st.text_input("Motif")
        if st.form_submit_button("Enregistrer"):
            _, err = api("POST", "/api/movements", json={
                "product_id": choix[produit], "type": type_, "quantite": int(quantite),
                "motif": motif, "date": datetime.now().isoformat()})  # fmt: skip
            st.error(err) if err else st.success("Mouvement enregistré.")


def page_assistant():
    st.title("Assistant")
    st.caption("Ex. : « Combien de bouteilles de Saint-Émilion 2018 reste-t-il ? » · "
               "« Quelles ont été les sorties de la semaine dernière ? »")  # fmt: skip
    if "chat" not in st.session_state:
        st.session_state["chat"] = []
    for role, texte, outils in st.session_state["chat"]:
        with st.chat_message(role):
            st.write(texte)
            if outils:
                st.caption(outils)
    if question := st.chat_input("Posez une question sur le stock…"):
        st.session_state["chat"].append(("user", question, ""))
        r, err = api("POST", "/api/assistant/ask", json={"question": question})
        if err:
            reponse, outils = f"Erreur : {err}", ""
        else:
            outils = f"mode {r['mode']}" + "".join(
                f" · outil {o['nom']} {o['arguments']}" for o in r["outils"]
            )
            reponse = r["reponse"]
        st.session_state["chat"].append(("assistant", reponse, outils))
        st.rerun()


PAGES = {"Tableau de bord": page_dashboard, "Produits": page_produits,
         "Mouvement": page_mouvement, "Assistant": page_assistant}  # fmt: skip

if "token" not in st.session_state:
    page_connexion()
else:
    if "user" not in st.session_state or st.session_state["user"] is None:
        st.session_state["user"], _ = api("GET", "/api/auth/me")
    with st.sidebar:
        st.title("🍷 Stock en cave")
        page = st.radio("Navigation", list(PAGES), label_visibility="collapsed")
        st.caption(f"{st.session_state['user']['email']} ({st.session_state['user']['role']})")
        if st.button("Déconnexion"):
            st.session_state.clear()
            st.rerun()
    PAGES[page]()
