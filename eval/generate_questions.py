"""Génère eval/questions.yaml : les réponses attendues sont calculées ICI, avec des boucles Python
simples sur les lignes de la base seed — volontairement SANS passer par les outils de l'assistant.

    python -m eval.generate_questions
"""

from datetime import date, datetime, timedelta
from pathlib import Path

import yaml
from sqlalchemy import select

from app.models import Product, StockMovement, TypeMouvement
from app.services.texte import normaliser
from eval.common import ANCHOR, base_eval

db = base_eval()
produits = list(db.scalars(select(Product)))
mouvements = list(db.scalars(select(StockMovement).order_by(StockMovement.date, StockMovement.id)))

stock = {p.id: 0 for p in produits}
for m in mouvements:
    stock[m.product_id] += -m.quantite if m.type == TypeMouvement.sortie else m.quantite


def total(filtre) -> int:
    return sum(stock[p.id] for p in produits if filtre(p))


def valeurs(filtre) -> tuple[int, int]:
    achat = sum(stock[p.id] * p.prix_achat for p in produits if filtre(p))
    vente = sum(stock[p.id] * p.prix_vente for p in produits if filtre(p))
    return int(achat), int(vente)  # partie entière


def contient(p: Product, mots: str) -> bool:
    return normaliser(mots) in normaliser(p.search_text)


def quantite(type_, debut: date, fin: date) -> int:
    borne_fin = datetime.combine(fin + timedelta(days=1), datetime.min.time())
    return sum(
        m.quantite
        for m in mouvements
        if m.type == type_ and datetime.combine(debut, datetime.min.time()) <= m.date < borne_fin
    )


lundi = ANCHOR - timedelta(days=ANCHOR.weekday())
sem_deb, sem_fin = lundi - timedelta(days=7), lundi - timedelta(days=1)
sous_seuil = [p for p in produits if stock[p.id] <= p.seuil_alerte]
figeac = next(p for p in produits if p.nom == "Château Figeac")
dernier_figeac = [m for m in mouvements if m.product_id == figeac.id][-1]
petrus = next(p for p in produits if p.nom == "Pétrus")

Q = []


def q(question, outil, chiffres=(), textes=()):
    Q.append({"question": question, "outil_attendu": outil,
              "chiffres": [str(c) for c in chiffres], "textes": list(textes)})  # fmt: skip


q("Combien de bouteilles de Saint-Émilion 2018 reste-t-il ?", "stock_produit",
  [total(lambda p: contient(p, "saint emilion") and p.millesime == 2018)])  # fmt: skip
q("Quels vins sont sous le seuil d'alerte ?", "produits_sous_seuil", [len(sous_seuil)])
q("Quelle est la valeur du stock de blancs ?", "resume_stock",
  valeurs(lambda p: p.couleur.value == "blanc"))  # fmt: skip
q("Quelles ont été les sorties de la semaine dernière ?", "mouvements_periode",
  [quantite(TypeMouvement.sortie, sem_deb, sem_fin)])  # fmt: skip
q("Combien de bouteilles de Champagne avons-nous en stock ?", "stock_produit",
  [total(lambda p: contient(p, "champagne"))])  # fmt: skip
q(
    "Quelle est la valeur totale du stock au prix d'achat ?",
    "resume_stock",
    [valeurs(lambda p: True)[0]],
)
q("Combien de bouteilles de rouge a-t-on en stock ?", "resume_stock",
  [total(lambda p: p.couleur.value == "rouge")])  # fmt: skip
q("Quels vins de Bourgogne sont sous le seuil d'alerte ?", "produits_sous_seuil",
  [sum(1 for p in sous_seuil if contient(p, "bourgogne"))])  # fmt: skip
q("Combien de bouteilles de Pétrus reste-t-il ?", "stock_produit", [stock[petrus.id]])
q("Quel est le total des entrées sur les 6 derniers mois ?", "mouvements_periode",
  [quantite(TypeMouvement.entree, ANCHOR - timedelta(days=182), ANCHOR)])  # fmt: skip
q("Quel est le stock total de bouteilles de la cave ?", "resume_stock", [total(lambda p: True)])
q("Quelle est la valeur du stock de la Vallée du Rhône au prix de vente ?", "resume_stock",
  [valeurs(lambda p: contient(p, "vallee du rhone"))[1]])  # fmt: skip
q("Quels sont les derniers mouvements de Château Figeac ?", "historique_produit",
  textes=[dernier_figeac.motif])  # fmt: skip
q("Quel temps fera-t-il demain à Grenoble ?", None)  # hors périmètre : aucun outil attendu
q("Combien il en reste ?", None)  # ambigu : aucun outil, demande de précision

sortie = Path(__file__).with_name("questions.yaml")
entete = (
    "# Généré par `python -m eval.generate_questions` depuis les données seed\n"
    f"# (ancre fixe : {ANCHOR}). Ne pas éditer à la main.\n"
    "# chiffres : nombres qui doivent apparaître dans la réponse ; textes : fragments attendus.\n"
    "# outil_attendu: null = l'assistant ne doit appeler aucun outil (hors périmètre / ambigu).\n"
)
sortie.write_text(entete + yaml.safe_dump(Q, allow_unicode=True, sort_keys=False, width=100))
print(f"{len(Q)} questions écrites dans {sortie}")
