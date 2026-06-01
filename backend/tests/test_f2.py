"""Test F2 — Personale ed Edifici (§4, §5, §6, §7, §8)."""
import random


# ─── helpers ─────────────────────────────────────────────────────────────────

def _auth(client, email="f2@x.com"):
    r = client.post("/api/auth/register", json={"email": email, "password": "secret1"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup(client, email="f2@x.com", culture="europea"):
    """Crea server + agenzia + recluta 1 pilota + 4 combattenti. Ritorna (headers, sid)."""
    h = _auth(client, email)
    sid = client.post("/api/admin/server", json={"name": "F2"}, headers=h).json()["id"]
    client.post("/api/agency", json={
        "server_id": sid, "name": "Agenzia F2", "culture": culture,
    }, headers=h)
    # aggiunge capitale per i test: esegui 0 tick (la grazia copre)
    client.post(f"/api/agency/{sid}/recruit",
                json={"option": "pilota_4_combattenti"}, headers=h)
    return h, sid


def _get_agency(client, h, sid):
    return client.get(f"/api/agency/{sid}", headers=h).json()


def _pilots(client, h, sid):
    return client.get(f"/api/agency/{sid}/pilots", headers=h).json()


def _fighters(client, h, sid):
    return client.get(f"/api/agency/{sid}/fighters", headers=h).json()


def _add_balance(client, sid, amount=50000):
    """Usa il tick per aggiungere giorni e costruire un saldo sufficiente ai test."""
    from app.database import SessionLocal
    from app.models.core import Agency
    db = SessionLocal()
    db.query(Agency).filter(Agency.server_id == sid).update({"balance": amount})
    db.commit()
    db.close()


# ─── §4.1 Caserma ─────────────────────────────────────────────────────────────

def test_upgrade_barracks(client):
    h, sid = _setup(client)
    _add_balance(client, sid)
    r = client.post(f"/api/agency/{sid}/buildings/barracks/upgrade", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["barracks_capacity"] == 20
    assert data["cost"] == 1000
    ag = _get_agency(client, h, sid)
    assert ag["barracks_capacity"] == 20


def test_upgrade_barracks_tutte_le_soglie(client):
    """Verifica che si possano raggiungere tutte le soglie di upgrade sequenzialmente."""
    h, sid = _setup(client)
    _add_balance(client, sid, 200000)
    thresholds = [20, 30, 40, 50, 80, 100]
    for expected in thresholds:
        r = client.post(f"/api/agency/{sid}/buildings/barracks/upgrade", headers=h)
        assert r.status_code == 200, f"upgrade a {expected} fallito: {r.text}"
        assert r.json()["barracks_capacity"] == expected
    # al massimo deve dare errore
    r = client.post(f"/api/agency/{sid}/buildings/barracks/upgrade", headers=h)
    assert r.status_code == 400


# ─── §5.1 Ospedale ────────────────────────────────────────────────────────────

def test_upgrade_hospital(client):
    h, sid = _setup(client)
    _add_balance(client, sid)
    r = client.post(f"/api/agency/{sid}/buildings/hospital/upgrade", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["hospital_capacity"] == 3


def test_hospitalize_and_discharge(client):
    h, sid = _setup(client)
    fighters = _fighters(client, h, sid)
    fid = fighters[0]["id"]

    # forza VIT basso per ammettere il combattente
    from app.database import SessionLocal
    from app.models.core import Fighter
    db = SessionLocal()
    db.query(Fighter).filter(Fighter.id == fid).update({"vit": 50})
    db.commit(); db.close()

    r = client.post(f"/api/agency/{sid}/fighters/{fid}/hospitalize", headers=h)
    assert r.status_code == 200, r.text

    # verifica status
    f = next(f for f in _fighters(client, h, sid) if f["id"] == fid)
    assert f["status"] == "hospital"

    # dimissione
    r = client.post(f"/api/agency/{sid}/fighters/{fid}/discharge", headers=h)
    assert r.status_code == 200, r.text
    f = next(f for f in _fighters(client, h, sid) if f["id"] == fid)
    assert f["status"] == "barracks"


def test_hospital_at_full_health_rejected(client):
    h, sid = _setup(client)
    fighters = _fighters(client, h, sid)
    fid = fighters[0]["id"]
    # combattente a piena salute (VIT=100 default)
    r = client.post(f"/api/agency/{sid}/fighters/{fid}/hospitalize", headers=h)
    assert r.status_code == 400


def test_hospital_capacity_limit(client):
    h, sid = _setup(client)
    _add_balance(client, sid)

    from app.database import SessionLocal
    from app.models.core import Fighter
    db = SessionLocal()
    db.query(Fighter).filter(Fighter.agency_id.in_(
        db.query(Fighter.agency_id).filter(Fighter.vit > 0).limit(1)
    )).update({"vit": 50})
    # imposta tutti i fighters a VIT 50
    fighters_data = _fighters(client, h, sid)
    ids = [f["id"] for f in fighters_data]
    db.query(Fighter).filter(Fighter.id.in_(ids)).update({"vit": 50})
    db.commit(); db.close()

    # l'ospedale ha capacità 2 di default
    r1 = client.post(f"/api/agency/{sid}/fighters/{ids[0]}/hospitalize", headers=h)
    assert r1.status_code == 200
    r2 = client.post(f"/api/agency/{sid}/fighters/{ids[1]}/hospitalize", headers=h)
    assert r2.status_code == 200
    r3 = client.post(f"/api/agency/{sid}/fighters/{ids[2]}/hospitalize", headers=h)
    assert r3.status_code == 400  # ospedale pieno


def test_hospital_tick_heals(client):
    """Il tick cura i combattenti in ospedale (§5.2)."""
    h, sid = _setup(client)

    from app.database import SessionLocal
    from app.models.core import Fighter
    db = SessionLocal()
    fighters_data = _fighters(client, h, sid)
    fid = fighters_data[0]["id"]
    db.query(Fighter).filter(Fighter.id == fid).update({"vit": 50, "status": "hospital"})
    db.commit(); db.close()

    client.post(f"/api/admin/server/{sid}/tick", headers=h)

    f = next(f for f in _fighters(client, h, sid) if f["id"] == fid)
    assert f["vit"] > 50  # curato dal tick


# ─── §7 Hangar ────────────────────────────────────────────────────────────────

def test_upgrade_hangar(client):
    h, sid = _setup(client)
    _add_balance(client, sid)
    r = client.post(f"/api/agency/{sid}/buildings/hangar/upgrade", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["hangar_slots"] == 4


def test_upgrade_hangar_prerequisito(client):
    """Lo slot 6 richiede almeno 1 aereo da caccia (§7)."""
    h, sid = _setup(client)
    _add_balance(client, sid, 500000)
    # porta l'hangar a 5 slot
    for _ in range(2):
        client.post(f"/api/agency/{sid}/buildings/hangar/upgrade", headers=h)
    ag = _get_agency(client, h, sid)
    assert ag["hangar_slots"] == 5
    # slot 6 richiede caccia — deve fallire
    r = client.post(f"/api/agency/{sid}/buildings/hangar/upgrade", headers=h)
    assert r.status_code == 400
    assert "caccia" in r.json()["detail"].lower()


# ─── §4.2 Licenze pilota ──────────────────────────────────────────────────────

def test_train_pilot_license_bronze(client):
    h, sid = _setup(client)
    _add_balance(client, sid)
    pilots = _pilots(client, h, sid)
    pid = pilots[0]["id"]

    r = client.post(f"/api/agency/{sid}/pilots/{pid}/train-license",
                    json={"license_type": "A", "tier": "bronze"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["license_type"] == "A"

    # pilota in training
    p = next(p for p in _pilots(client, h, sid) if p["id"] == pid)
    assert p["status"] == "training"
    assert p["training_info"] == "lic:A:bronze"


def test_train_pilot_license_skip_tier_rejected(client):
    h, sid = _setup(client)
    _add_balance(client, sid)
    pilots = _pilots(client, h, sid)
    pid = pilots[0]["id"]
    # tenta silver senza bronze — deve fallire
    r = client.post(f"/api/agency/{sid}/pilots/{pid}/train-license",
                    json={"license_type": "A", "tier": "silver"}, headers=h)
    assert r.status_code == 400


def test_train_pilot_license_completes_on_tick(client):
    """Dopo training_until_day tick, il pilota ottiene la licenza."""
    h, sid = _setup(client)
    _add_balance(client, sid, 50000)
    pilots = _pilots(client, h, sid)
    pid = pilots[0]["id"]

    # licenza C-Bronze dura 1 giorno
    client.post(f"/api/agency/{sid}/pilots/{pid}/train-license",
                json={"license_type": "C", "tier": "bronze"}, headers=h)

    # avanza 1 giorno (training_until_day = 0 + 1 = 1, tick porta a 1)
    client.post(f"/api/admin/server/{sid}/tick", headers=h)

    p = next(p for p in _pilots(client, h, sid) if p["id"] == pid)
    assert p["status"] == "barracks"
    assert p["licenses"].get("C") == "bronze"


def test_perk_europea_license_time(client):
    """Perk Europea: -25% tempo licenza (§1.1)."""
    h, sid = _setup(client, email="eu2@x.com", culture="europea")
    _add_balance(client, sid)
    pilots = _pilots(client, h, sid)
    pid = pilots[0]["id"]
    # licenza B-Bronze dura 2 giorni → con -25% = ceil(1.5) = 2 → ancora 2
    # licenza A-Silver dura 5 giorni → con -25% = ceil(3.75) = 4
    r = client.post(f"/api/agency/{sid}/pilots/{pid}/train-license",
                    json={"license_type": "A", "tier": "bronze"}, headers=h)
    assert r.status_code == 200
    # A-Bronze dura 1g → con -25% = ceil(0.75) = 1
    assert r.json()["giorni_addestramento"] == 1


# ─── §4.3 Addestramento stat pilota ──────────────────────────────────────────

def test_train_pilot_stat(client):
    h, sid = _setup(client)
    _add_balance(client, sid)
    pilots = _pilots(client, h, sid)
    pid = pilots[0]["id"]
    espo_old = pilots[0]["espo_pct"]

    r = client.post(f"/api/agency/{sid}/pilots/{pid}/train-stat",
                    json={"stat": "espo"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["stat"] == "espo"

    # tick completa training
    client.post(f"/api/admin/server/{sid}/tick", headers=h)
    p = next(p for p in _pilots(client, h, sid) if p["id"] == pid)
    assert p["espo_pct"] == round(espo_old + 1.0, 1)
    assert p["status"] == "barracks"


# ─── §4.4 Addestramento combattenti ──────────────────────────────────────────

def test_train_fighter_stat(client):
    h, sid = _setup(client)
    _add_balance(client, sid)
    fighters = _fighters(client, h, sid)
    fid = fighters[0]["id"]
    str_old = fighters[0]["str"]

    r = client.post(f"/api/agency/{sid}/fighters/{fid}/train",
                    json={"stat": "STR"}, headers=h)
    assert r.status_code == 200, r.text

    # tick completa training
    client.post(f"/api/admin/server/{sid}/tick", headers=h)
    f = next(f for f in _fighters(client, h, sid) if f["id"] == fid)
    assert f["str"] == str_old + 1
    assert f["status"] == "barracks"


def test_train_fighter_stat_cap(client):
    """Non si può superare il cap (§4.4)."""
    h, sid = _setup(client)
    _add_balance(client, sid)
    fighters = _fighters(client, h, sid)
    fid = fighters[0]["id"]

    from app.database import SessionLocal
    from app.models.core import Fighter
    db = SessionLocal()
    db.query(Fighter).filter(Fighter.id == fid).update({"mov": 25})
    db.commit(); db.close()

    r = client.post(f"/api/agency/{sid}/fighters/{fid}/train",
                    json={"stat": "MOV"}, headers=h)
    assert r.status_code == 400


# ─── §6.1 Equipaggiamento combattenti ─────────────────────────────────────────

def test_equip_fighter_weapon(client):
    h, sid = _setup(client)
    _add_balance(client, sid)
    fighters = _fighters(client, h, sid)
    fid = fighters[0]["id"]

    r = client.post(f"/api/agency/{sid}/fighters/{fid}/equip",
                    json={"slot": "weapon", "level_key": "bronze1"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["slot"] == "weapon"
    assert r.json()["level_key"] == "bronze1"

    # verifica persistenza
    f = next(f for f in _fighters(client, h, sid) if f["id"] == fid)
    assert f["equipment"]["weapon"]["key"] == "bronze1"


def test_equip_fighter_remove(client):
    h, sid = _setup(client)
    _add_balance(client, sid)
    fighters = _fighters(client, h, sid)
    fid = fighters[0]["id"]

    # equip
    client.post(f"/api/agency/{sid}/fighters/{fid}/equip",
                json={"slot": "weapon", "level_key": "bronze1"}, headers=h)

    # rimozione gratuita
    r = client.post(f"/api/agency/{sid}/fighters/{fid}/equip",
                    json={"slot": "weapon", "level_key": ""}, headers=h)
    assert r.status_code == 200
    assert r.json()["level_key"] is None


# ─── §8 Acquisto vettori ──────────────────────────────────────────────────────

def test_buy_vehicle(client):
    h, sid = _setup(client)
    _add_balance(client, sid)
    ag = _get_agency(client, h, sid)
    initial_balance = ag["balance"]

    r = client.post(f"/api/agency/{sid}/vehicles/buy",
                    json={"project": "Dubai"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["project"] == "Dubai"
    assert r.json()["vclass"] == "exploration"

    ag2 = _get_agency(client, h, sid)
    assert ag2["balance"] < initial_balance  # saldo scalato


def test_buy_vehicle_hangar_full(client):
    """Hangar pieno (3 slot di default) blocca ulteriori acquisti."""
    h, sid = _setup(client)
    _add_balance(client, sid, 500000)
    for _ in range(3):
        client.post(f"/api/agency/{sid}/vehicles/buy", json={"project": "Dubai"}, headers=h)
    r = client.post(f"/api/agency/{sid}/vehicles/buy", json={"project": "Dubai"}, headers=h)
    assert r.status_code == 400


def test_buy_vehicle_nordamericana_discount(client):
    """Perk Nordamericana: -10% su aerei (§1.1)."""
    h, sid = _setup(client, email="na@x.com", culture="nordamericana")
    _add_balance(client, sid)
    r = client.post(f"/api/agency/{sid}/vehicles/buy",
                    json={"project": "Dubai"}, headers=h)
    assert r.status_code == 200
    # Dubai costa 100R, con sconto -10% = 90R
    assert r.json()["cost"] == 90


def test_assign_pilot_to_vehicle(client):
    h, sid = _setup(client)
    _add_balance(client, sid)

    # compra un veicolo
    vid = client.post(f"/api/agency/{sid}/vehicles/buy",
                      json={"project": "Dubai"}, headers=h).json()["vehicle_id"]

    # allena il pilota sulla licenza A-Bronze (1g, poi tick)
    pilots = _pilots(client, h, sid)
    pid = pilots[0]["id"]
    client.post(f"/api/agency/{sid}/pilots/{pid}/train-license",
                json={"license_type": "A", "tier": "bronze"}, headers=h)
    client.post(f"/api/admin/server/{sid}/tick", headers=h)  # completa addestramento

    # assegna
    r = client.post(f"/api/agency/{sid}/vehicles/{vid}/assign-pilot",
                    json={"pilot_id": pid}, headers=h)
    assert r.status_code == 200, r.text

    v = next(v for v in client.get(f"/api/agency/{sid}/vehicles", headers=h).json()
             if v["id"] == vid)
    assert v["pilot_id"] == pid


def test_assign_pilot_wrong_license(client):
    """Pilota senza licenza non può pilotare il vettore."""
    h, sid = _setup(client)
    _add_balance(client, sid)
    vid = client.post(f"/api/agency/{sid}/vehicles/buy",
                      json={"project": "Dubai"}, headers=h).json()["vehicle_id"]
    pilots = _pilots(client, h, sid)
    pid = pilots[0]["id"]
    # il pilota non ha licenza A — deve fallire
    r = client.post(f"/api/agency/{sid}/vehicles/{vid}/assign-pilot",
                    json={"pilot_id": pid}, headers=h)
    assert r.status_code == 400


# ─── §6.2 Missili ─────────────────────────────────────────────────────────────

def test_load_missiles(client):
    h, sid = _setup(client, email="mis@x.com", culture="nordamericana")
    _add_balance(client, sid)

    # compra un aereo da caccia (serve B-Bronze; Nordamericana — perk sconto non aiuta sulla licenza)
    # usiamo direttamente il DB per creare il vettore senza controllo licenza
    from app.database import SessionLocal
    from app.models.core import Vehicle as V
    db = SessionLocal()
    from app.models.core import Agency as Ag
    ag_id = db.query(Ag).filter(Ag.server_id == sid).first().id
    v = V(agency_id=ag_id, project="Tikal", vclass="fighter")
    db.add(v)
    db.commit()
    vid = v.id
    db.close()

    r = client.post(f"/api/agency/{sid}/vehicles/{vid}/missiles",
                    json={"missile_key": "bronze", "count": 2, "missile_type": "terra"},
                    headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["missiles"]["terra"]["count"] == 2
    assert r.json()["missiles"]["terra"]["key"] == "bronze"


def test_load_missiles_exceeds_max(client):
    h, sid = _setup(client, email="mis2@x.com")
    _add_balance(client, sid)

    from app.database import SessionLocal
    from app.models.core import Agency as Ag, Vehicle as V
    db = SessionLocal()
    ag_id = db.query(Ag).filter(Ag.server_id == sid).first().id
    v = V(agency_id=ag_id, project="Tikal", vclass="fighter")
    db.add(v); db.commit(); vid = v.id; db.close()

    # carica 3 terra + 2 spazio = 5 > 4 → errore
    client.post(f"/api/agency/{sid}/vehicles/{vid}/missiles",
                json={"missile_key": "bronze", "count": 3, "missile_type": "terra"}, headers=h)
    r = client.post(f"/api/agency/{sid}/vehicles/{vid}/missiles",
                    json={"missile_key": "bronze", "count": 2, "missile_type": "spazio"},
                    headers=h)
    assert r.status_code == 400


# ─── §7 Hangar + prerequisiti ────────────────────────────────────────────────

def test_upgrade_hangar_after_buying_fighter(client):
    """Con un aereo da caccia, lo slot 6 si sblocca."""
    h, sid = _setup(client)
    _add_balance(client, sid, 1000000)

    # porta a 5 slot senza prerequisiti
    for _ in range(2):
        client.post(f"/api/agency/{sid}/buildings/hangar/upgrade", headers=h)

    # inserisce un aereo da caccia via DB
    from app.database import SessionLocal
    from app.models.core import Agency as Ag, Vehicle as V
    db = SessionLocal()
    ag_id = db.query(Ag).filter(Ag.server_id == sid).first().id
    v = V(agency_id=ag_id, project="Tikal", vclass="fighter")
    db.add(v); db.commit(); db.close()

    # ora slot 6 disponibile
    r = client.post(f"/api/agency/{sid}/buildings/hangar/upgrade", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["hangar_slots"] == 6


# ─── Tick integrato F2 ────────────────────────────────────────────────────────

def test_tick_vit_regen_barracks(client):
    """VIT +1/g gratis in caserma, max 120 (§4.4)."""
    h, sid = _setup(client)

    from app.database import SessionLocal
    from app.models.core import Fighter
    db = SessionLocal()
    fighters_data = _fighters(client, h, sid)
    fid = fighters_data[0]["id"]
    db.query(Fighter).filter(Fighter.id == fid).update({"vit": 90, "status": "barracks"})
    db.commit(); db.close()

    client.post(f"/api/admin/server/{sid}/tick", headers=h)
    f = next(f for f in _fighters(client, h, sid) if f["id"] == fid)
    assert f["vit"] == 91
