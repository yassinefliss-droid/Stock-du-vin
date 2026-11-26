from datetime import date

import pytest

from app.models import TypeMouvement
from app.services import stock as svc
from app.services.erreurs import Introuvable, StockInsuffisant


def test_stock_calcule_depuis_les_mouvements(db, cave):
    # entrée 20 − sortie 5 + ajustement +2
    assert svc.stock_courant(db, cave["figeac"].id) == 17
    assert svc.stock_courant(db, cave["angelus"].id) == 3


def test_produit_sans_mouvement_a_un_stock_nul(db, cave):
    from app.models import Couleur
    from tests.conftest import produit

    p = produit(db, "X", "Vin neuf", "Chinon", "Loire", Couleur.rouge, 2021, 10, 15)
    assert svc.stock_courant(db, p.id) == 0
    assert {x.produit.id: x.stock for x in svc.lister(db)}[p.id] == 0


def test_sortie_superieure_au_stock_refusee(db, cave):
    with pytest.raises(StockInsuffisant):
        svc.enregistrer_mouvement(
            db, product_id=cave["angelus"].id, type=TypeMouvement.sortie, quantite=4
        )
    assert svc.stock_courant(db, cave["angelus"].id) == 3  # rien n'a été enregistré


def test_sortie_exacte_autorisee_jusqu_a_zero(db, cave):
    svc.enregistrer_mouvement(
        db, product_id=cave["angelus"].id, type=TypeMouvement.sortie, quantite=3
    )
    assert svc.stock_courant(db, cave["angelus"].id) == 0


def test_ajustement_negatif_ne_peut_pas_rendre_le_stock_negatif(db, cave):
    with pytest.raises(StockInsuffisant):
        svc.enregistrer_mouvement(
            db, product_id=cave["angelus"].id, type=TypeMouvement.ajustement, quantite=-4
        )
    svc.enregistrer_mouvement(
        db, product_id=cave["angelus"].id, type=TypeMouvement.ajustement, quantite=-2
    )
    assert svc.stock_courant(db, cave["angelus"].id) == 1


def test_produit_inconnu(db):
    with pytest.raises(Introuvable):
        svc.enregistrer_mouvement(db, product_id=999, type=TypeMouvement.entree, quantite=1)


def test_alertes_seuil_atteint_ou_depasse(db, cave):
    noms = {x.produit.reference for x in svc.lister(db, sous_seuil=True)}
    assert noms == {"ANG-18", "KRU-NM"}  # stock 3 et 4, seuil 5


def test_valeur_du_stock(db, cave):
    v = svc.valeur(svc.lister(db))
    # bouteilles : 17 + 3 + 10 + 4
    assert v.bouteilles == 34
    assert v.valeur_achat == 17 * 100 + 3 * 200 + 10 * 40 + 4 * 140
    assert v.valeur_vente == 17 * 150 + 3 * 300 + 10 * 60 + 4 * 200


def test_recherche_sans_accents_ni_tirets(db, cave):
    lignes = svc.lister(db, svc.Filtre(recherche="saint emilion", millesime=2018))
    assert len(lignes) == 2


def test_historique_filtre_par_periode_bornes_incluses(db, cave):
    mouvements = svc.historique(db, debut=date(2025, 6, 12), fin=date(2025, 6, 16))
    assert sorted(m.quantite for m in mouvements) == [2, 5]  # 11/06 et 17/06 exclus
    pour_figeac = svc.historique(db, product_id=cave["figeac"].id)
    assert len(pour_figeac) == 3
    assert pour_figeac[0].type == TypeMouvement.ajustement  # le plus récent d'abord
