"""Mise en forme française des résultats d'outils (mode règles)."""


def eur(x: float) -> str:
    return f"{x:,.2f}".replace(",", " ").replace(".", ",") + " €"


def _nom(p: dict) -> str:
    return f"{p['nom']} {p['millesime'] or 'NM'} ({p['format']})"


def _liste_produits(produits: list[dict], total: int) -> str:
    lignes = [
        f"- {_nom(p)} : {p['stock']} bouteille(s) (seuil {p['seuil_alerte']})" for p in produits
    ]
    if total > len(produits):
        lignes.append(f"… et {total - len(produits)} autre(s).")
    return "\n".join(lignes)


def formater(outil: str, r: dict) -> str:
    if "erreur" in r:
        return f"Je n'ai pas pu interroger le stock : {r['erreur']}"

    if outil == "stock_produit":
        if not r["nombre_produits"]:
            return "Aucun produit ne correspond à cette recherche."
        entete = f"Il reste {r['total_bouteilles']} bouteille(s) au total ({r['nombre_produits']} référence(s)) :"
        return entete + "\n" + _liste_produits(r["produits"], r["nombre_produits"])

    if outil == "produits_sous_seuil":
        if not r["nombre_produits"]:
            return "Aucun produit n'est sous le seuil d'alerte."
        entete = f"{r['nombre_produits']} produit(s) sous le seuil d'alerte :"
        return entete + "\n" + _liste_produits(r["produits"], r["nombre_produits"])

    if outil == "resume_stock":
        if not r["nombre_references"]:
            return "Aucun produit ne correspond à ce filtre."
        return (
            f"{r['total_bouteilles']} bouteille(s) sur {r['nombre_references']} référence(s). "
            f"Valeur au prix d'achat : {eur(r['valeur_achat_eur'])} ; "
            f"au prix de vente : {eur(r['valeur_vente_eur'])}."
        )

    if outil == "mouvements_periode":
        periode = f"du {r['debut'] or '…'} au {r['fin'] or '…'}"
        if not r["nombre_mouvements"]:
            return f"Aucun mouvement {periode}."
        types = ", ".join(f"{t} : {q} bouteille(s)" for t, q in r["quantite_par_type"].items())
        top = "\n".join(f"- {x['nom']} : {x['quantite']}" for x in r["produits_les_plus_concernes"])
        return (
            f"{r['nombre_mouvements']} mouvement(s) {periode} ({types}).\n"
            f"Produits les plus concernés :\n{top}"
        )

    if outil == "historique_produit":
        if not r["mouvements"]:
            return "Aucun mouvement trouvé pour ce produit."
        lignes = [
            f"- {m['date']} {m['type']} {m['quantite']} × {m['produit']} {m['millesime'] or ''}"
            f" — {m['motif']}"
            for m in r["mouvements"]
        ]
        return "Derniers mouvements :\n" + "\n".join(lignes)

    return str(r)
