from app.models import Role

NOUVEAU = {
    "reference": "NEW-1", "nom": "Vin test", "domaine": "Domaine test", "appellation": "Chinon",
    "region": "Loire", "millesime": 2021, "couleur": "rouge", "prix_achat": "10.50",
    "prix_vente": "16.00", "seuil_alerte": 4,
}  # fmt: skip


def test_login_et_acces(client, users):
    r = client.post(
        "/api/auth/token", data={"username": "admin@test.fr", "password": "motdepasse1"}
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["role"] == "admin"


def test_mauvais_mot_de_passe(client, users):
    r = client.post("/api/auth/token", data={"username": "admin@test.fr", "password": "faux"})
    assert r.status_code == 401


def test_api_protegee(client, cave):
    assert client.get("/api/products").status_code == 401
    assert (
        client.get("/api/products", headers={"Authorization": "Bearer nimportequoi"}).status_code
        == 401
    )


def test_lecture_seule_ne_peut_rien_modifier(client, cave, auth):
    h = auth[Role.lecture_seule]
    assert client.get("/api/products", headers=h).status_code == 200  # lecture OK
    assert client.post("/api/products", json=NOUVEAU, headers=h).status_code == 403
    pid = cave["figeac"].id
    assert client.put(f"/api/products/{pid}", json={"nom": "X"}, headers=h).status_code == 403
    assert client.delete(f"/api/products/{pid}", headers=h).status_code == 403
    mvt = {"product_id": pid, "type": "entree", "quantite": 1}
    assert client.post("/api/movements", json=mvt, headers=h).status_code == 403


def test_gestionnaire_ecrit_mais_ne_supprime_pas_ni_ne_gere_les_utilisateurs(client, cave, auth):
    h = auth[Role.gestionnaire]
    assert client.post("/api/products", json=NOUVEAU, headers=h).status_code == 201
    pid = cave["figeac"].id
    assert (
        client.put(f"/api/products/{pid}", json={"seuil_alerte": 9}, headers=h).status_code == 200
    )
    assert client.delete(f"/api/products/{pid}", headers=h).status_code == 403
    assert client.get("/api/users", headers=h).status_code == 403


def test_seul_admin_gere_les_utilisateurs(client, auth):
    h = auth[Role.admin]
    assert client.get("/api/users", headers=h).status_code == 200
    r = client.post(
        "/api/users",
        json={"email": "nouveau@test.fr", "password": "unmotdepasse", "role": "gestionnaire"},
        headers=h,
    )
    assert r.status_code == 201
    uid = r.json()["id"]
    assert (
        client.patch(f"/api/users/{uid}", json={"actif": False}, headers=h).json()["actif"] is False
    )
    # un compte désactivé ne peut plus se connecter
    r = client.post(
        "/api/auth/token", data={"username": "nouveau@test.fr", "password": "unmotdepasse"}
    )
    assert r.status_code == 401
    # un email en double est refusé
    r = client.post(
        "/api/users", json={"email": "nouveau@test.fr", "password": "unmotdepasse"}, headers=h
    )
    assert r.status_code == 409


def test_crud_produit(client, auth):
    h = auth[Role.admin]
    r = client.post("/api/products", json=NOUVEAU, headers=h)
    assert r.status_code == 201
    pid = r.json()["id"]
    assert client.post("/api/products", json=NOUVEAU, headers=h).status_code == 409  # doublon
    assert client.get(f"/api/products/{pid}", headers=h).json()["nom"] == "Vin test"
    r = client.put(f"/api/products/{pid}", json={"prix_vente": "18.00"}, headers=h)
    assert r.json()["prix_vente"] == "18.00"
    assert client.delete(f"/api/products/{pid}", headers=h).status_code == 204
    assert client.get(f"/api/products/{pid}", headers=h).status_code == 404


def test_produit_invalide(client, auth):
    r = client.post("/api/products", json={**NOUVEAU, "prix_achat": "-3"}, headers=auth[Role.admin])
    assert r.status_code == 422


def test_suppression_refusee_si_historique(client, cave, auth):
    r = client.delete(f"/api/products/{cave['figeac'].id}", headers=auth[Role.admin])
    assert r.status_code == 409


def test_mouvement_et_refus_de_stock_negatif(client, cave, auth):
    h = auth[Role.gestionnaire]
    pid = cave["angelus"].id  # stock 3
    r = client.post(
        "/api/movements", json={"product_id": pid, "type": "sortie", "quantite": 5}, headers=h
    )
    assert r.status_code == 409
    assert "insuffisant" in r.json()["detail"]
    r = client.post(
        "/api/movements", json={"product_id": pid, "type": "entree", "quantite": 10}, headers=h
    )
    assert r.status_code == 201
    assert client.get(f"/api/products/{pid}/stock", headers=h).json()["stock"] == 13


def test_mouvement_invalide(client, cave, auth):
    h = auth[Role.admin]
    pid = cave["angelus"].id
    for corps in (
        {"product_id": pid, "type": "sortie", "quantite": 0},
        {"product_id": pid, "type": "entree", "quantite": -2},
        {"product_id": pid, "type": "ajustement", "quantite": 0},
        {"product_id": 9999, "type": "entree", "quantite": 1},
    ):
        assert client.post("/api/movements", json=corps, headers=h).status_code in (404, 422)


def test_stock_alertes_et_valeur(client, cave, auth):
    h = auth[Role.lecture_seule]
    alertes = client.get("/api/stock/alertes", headers=h).json()
    assert {a["reference"] for a in alertes} == {"ANG-18", "KRU-NM"}
    v = client.get("/api/stock/valeur", headers=h).json()
    assert v["bouteilles"] == 34 and float(v["valeur_vente"]) == 17 * 150 + 900 + 600 + 800
    blancs = client.get("/api/stock/valeur?couleur=blanc", headers=h).json()
    assert blancs["bouteilles"] == 10 and float(blancs["valeur_achat"]) == 400


def test_liste_filtrable(client, cave, auth):
    h = auth[Role.lecture_seule]
    r = client.get("/api/products?recherche=saint-émilion&millesime=2018", headers=h).json()
    assert {p["reference"]: p["stock"] for p in r} == {"FIG-18": 17, "ANG-18": 3}
    assert len(client.get("/api/products?couleur=blanc", headers=h).json()) == 1


def test_historique_filtre_produit_et_periode(client, cave, auth):
    h = auth[Role.lecture_seule]
    pid = cave["figeac"].id
    r = client.get(f"/api/movements?product_id={pid}", headers=h).json()
    assert len(r) == 3
    r = client.get(
        f"/api/movements?product_id={pid}&date_debut=2025-06-01&date_fin=2025-06-13", headers=h
    ).json()
    assert [m["quantite"] for m in r] == [5]
