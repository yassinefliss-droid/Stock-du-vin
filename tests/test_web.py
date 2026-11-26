from app.models import Role
from app.services import stock as svc


def connecte(client, role):
    r = client.post("/login", data={"email": f"{role.value}@test.fr", "password": "motdepasse1"})
    assert r.status_code == 303
    return client


def test_pages_protegees_redirigent_vers_login(client):
    for url in ("/dashboard", "/produits", "/assistant", "/mouvements/nouveau"):
        r = client.get(url)
        assert r.status_code == 303 and r.headers["location"] == "/login"


def test_login_refuse(client, users):
    r = client.post("/login", data={"email": "admin@test.fr", "password": "mauvais"})
    assert r.status_code == 401 and "incorrect" in r.text


def test_dashboard_produits_et_fiche(client, cave, users):
    connecte(client, Role.admin)
    page = client.get("/dashboard").text
    assert "34" in page and "Château Angélus" in page  # stock total + alerte
    assert "Château Figeac" in client.get("/produits?recherche=figeac").text
    assert "Château Figeac" not in client.get("/produits?couleur=blanc").text
    fiche = client.get(f"/produits/{cave['figeac'].id}").text
    assert "Inventaire" in fiche and "Stock initial" in fiche
    assert client.get("/produits/9999").status_code == 404


def test_formulaire_de_mouvement(client, cave, users, db):
    connecte(client, Role.gestionnaire)
    pid = cave["angelus"].id
    r = client.post(
        "/mouvements/nouveau", data={"product_id": pid, "type": "entree", "quantite": 7}
    )
    assert r.status_code == 303
    assert svc.stock_courant(db, pid) == 10
    r = client.post(
        "/mouvements/nouveau", data={"product_id": pid, "type": "sortie", "quantite": 50}
    )
    assert r.status_code == 409 and "insuffisant" in r.text


def test_lecture_seule_ne_peut_pas_enregistrer_via_le_web(client, cave, users, db):
    connecte(client, Role.lecture_seule)
    pid = cave["angelus"].id
    r = client.post(
        "/mouvements/nouveau", data={"product_id": pid, "type": "entree", "quantite": 7}
    )
    assert r.status_code == 403
    assert svc.stock_courant(db, pid) == 3
    assert "Mouvement" not in client.get("/dashboard").text  # lien masqué dans le menu


def test_page_assistant(client, cave, users):
    connecte(client, Role.lecture_seule)
    r = client.post("/assistant", data={"question": "Quelle est la valeur du stock de blancs ?"})
    assert r.status_code == 200 and "400,00 €" in r.text and "resume_stock" in r.text


def test_deconnexion(client, users):
    connecte(client, Role.admin)
    client.post("/logout")
    client.cookies.clear()
    assert client.get("/dashboard").status_code == 303
