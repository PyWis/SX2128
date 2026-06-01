"""Test di integrazione del vertical slice F0+F1 (auth -> server -> agenzia -> recluta -> tick)."""


def _auth(client, email="g@x.com"):
    r = client.post("/api/auth/register", json={"email": email, "password": "secret1"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_catalog_cultures(client):
    r = client.get("/api/catalog/cultures")
    assert r.status_code == 200
    assert len(r.json()) == 10


def test_catalog_vehicles(client):
    r = client.get("/api/catalog/vehicles")
    assert r.status_code == 200
    # 10+10+10+10+10+3 = 53 progetti (§8.1-8.6)
    assert len(r.json()) == 53


def test_full_flow(client):
    h = _auth(client)
    r = client.post("/api/admin/server", json={"name": "Alpha", "server_type": "f2p"}, headers=h)
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    # crea agenzia (Europea: base 250, +3%/g)
    r = client.post("/api/agency", json={
        "server_id": sid, "name": "Difensori", "culture": "europea",
        "base_lat": 41.9, "base_lon": 12.5,
    }, headers=h)
    assert r.status_code == 200, r.text
    ag = r.json()
    assert ag["balance"] == 2000        # §0.2 capitale iniziale
    assert ag["barracks_capacity"] == 10
    assert ag["hangar_slots"] == 3

    # reclutamento: pilota + 2 combattenti (200 R)
    r = client.post(f"/api/agency/{sid}/recruit",
                    json={"option": "pilota_2_combattenti"}, headers=h)
    assert r.status_code == 200, r.text
    assert len(r.json()["pilots"]) == 1
    assert len(r.json()["fighters"]) == 2

    # secondo reclutamento stesso giorno -> vietato (§3)
    r = client.post(f"/api/agency/{sid}/recruit", json={"option": "1_combattente"}, headers=h)
    assert r.status_code == 400

    # stato agenzia: saldo scalato
    r = client.get(f"/api/agency/{sid}", headers=h)
    assert r.json()["balance"] == 1800

    # avanza di un giorno
    r = client.post(f"/api/admin/server/{sid}/tick", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["day"] == 1

    r = client.get(f"/api/agency/{sid}", headers=h)
    body = r.json()
    assert body["loyalty_days"] == 1
    assert body["balance"] > 1800       # netto giornaliero positivo
    assert body["missions_completed"] == 0


def test_hangar_perk_cinese(client):
    h = _auth(client, "c@x.com")
    sid = client.post("/api/admin/server", json={"name": "B"}, headers=h).json()["id"]
    r = client.post("/api/agency", json={
        "server_id": sid, "name": "Drago", "culture": "cinese",
    }, headers=h)
    # perk Cinese: hangar 3 + 2 = 5 (§1.1)
    assert r.json()["hangar_slots"] == 5


def test_capienza_server(client, monkeypatch):
    # riduce la capacita per testare il limite senza creare 256 agenzie
    h = _auth(client, "cap@x.com")
    sid = client.post("/api/admin/server", json={"name": "C"}, headers=h).json()["id"]
    from app.database import SessionLocal
    from app.models.core import Server
    db = SessionLocal()
    db.query(Server).filter(Server.id == sid).update({"capacity": 1})
    db.commit(); db.close()
    r1 = client.post("/api/agency", json={"server_id": sid, "name": "A1", "culture": "europea"}, headers=h)
    assert r1.status_code == 200
    h2 = _auth(client, "cap2@x.com")
    r2 = client.post("/api/agency", json={"server_id": sid, "name": "A2", "culture": "cinese"}, headers=h2)
    assert r2.status_code == 400  # server al completo
