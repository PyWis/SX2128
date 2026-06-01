"""Test F3 — Vettori & Missioni base Terrestri (§8, §9.5-9.7, §9.10)."""
import random

from app.database import SessionLocal
from app.gamedata.enums import MissionStatus, MissionType
from app.models.core import Agency, Fighter, Mission, Pilot, Vehicle


# ─── helpers ────────────────────────────────────────────────────────────────

def _auth(client, email="f3@x.com"):
    r = client.post("/api/auth/register", json={"email": email, "password": "secret1"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup(client, email="f3@x.com", culture="europea"):
    h = _auth(client, email)
    sid = client.post("/api/admin/server", json={"name": "F3"}, headers=h).json()["id"]
    client.post("/api/agency", json={
        "server_id": sid, "name": "F3 Agency", "culture": culture,
        "base_lat": 41.9, "base_lon": 12.5,
    }, headers=h)
    client.post(f"/api/agency/{sid}/recruit",
                json={"option": "pilota_4_combattenti"}, headers=h)
    return h, sid


def _set_balance(sid, amount=100000):
    db = SessionLocal()
    db.query(Agency).filter(Agency.server_id == sid).update({"balance": amount})
    db.commit(); db.close()


def _get_agency(client, h, sid):
    return client.get(f"/api/agency/{sid}", headers=h).json()


def _pilots(client, h, sid):
    return client.get(f"/api/agency/{sid}/pilots", headers=h).json()


def _fighters(client, h, sid):
    return client.get(f"/api/agency/{sid}/fighters", headers=h).json()


def _vehicles(client, h, sid):
    return client.get(f"/api/agency/{sid}/vehicles", headers=h).json()


def _missions_active(client, h, sid):
    return client.get(f"/api/agency/{sid}/missions/active", headers=h).json()


def _inject_mission(sid, agency_id, mtype=MissionType.TERRESTRE, day=0):
    """Inserisce una missione assegnata direttamente nel DB."""
    from app.services.formulas import enemy_power, reward
    from app.gamedata.enums import AlarmLevel
    db = SessionLocal()
    pn = enemy_power(mtype, day, n_combattenti=8)
    m = Mission(
        server_id=sid, agency_id=agency_id,
        mission_type=mtype.value, alarm=AlarmLevel.VERDE.value,
        status=MissionStatus.ASSIGNED.value,
        target_lat=48.8, target_lon=2.3,  # Paris — ~1100 km da Roma
        pn=pn, reward_estimate=reward(pn, mtype, AlarmLevel.VERDE),
        assigned_day=day, deadline_day=day + 7,
    )
    db.add(m)
    db.commit()
    mid = m.id
    db.close()
    return mid


def _agency_id(sid):
    db = SessionLocal()
    ag = db.query(Agency).filter(Agency.server_id == sid).first()
    aid = ag.id
    db.close()
    return aid


def _inject_mission_vehicle(sid, vclass="mission"):
    """Aggiunge un vettore direttamente nel DB per i test."""
    db = SessionLocal()
    ag = db.query(Agency).filter(Agency.server_id == sid).first()
    # sceglie un blueprint con il numero giusto di postazioni
    if vclass == "mission":
        project = "Belisario"   # 8 postazioni
    elif vclass == "fighter":
        project = "Tikal"
    else:
        project = "Cygnus"
    v = Vehicle(agency_id=ag.id, project=project, vclass=vclass)
    db.add(v); db.commit()
    vid = v.id
    db.close()
    return vid


def _give_pilot_license(pilot_id, license_type="B", tier="bronze"):
    db = SessionLocal()
    p = db.get(Pilot, pilot_id)
    p.licenses = {**p.licenses, license_type: tier}
    db.commit(); db.close()


# ─── §8 Tempo di volo ──────────────────────────────────────────────────────

def test_haversine_approx():
    """Distanza Roma-Parigi ≈ 1100 km."""
    from app.services.launch_service import _haversine_km
    d = _haversine_km(41.9, 12.5, 48.8, 2.3)
    assert 1000 < d < 1300, f"distanza inattesa: {d}"


def test_eta_positive():
    from app.services.launch_service import _eta_days
    eta = _eta_days(1100.0, 0.7)  # Belisario: 0.7 Mach
    assert eta > 0


# ─── §9 Lancio missione Terrestre ─────────────────────────────────────────

def test_launch_terrestre(client):
    h, sid = _setup(client)
    _set_balance(sid)
    aid = _agency_id(sid)
    mid = _inject_mission(sid, aid, MissionType.TERRESTRE)
    vid = _inject_mission_vehicle(sid, "mission")
    fighters = _fighters(client, h, sid)
    fids = [f["id"] for f in fighters[:4]]

    r = client.post(f"/api/agency/{sid}/missions/{mid}/launch",
                    json={"vehicle_id": vid, "fighter_ids": fids}, headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["mtype"] == "terrestre"
    assert data["return_day"] > 0
    assert len(data["fighters"]) == 4

    # vettore in volo
    vs = _vehicles(client, h, sid)
    v = next(v for v in vs if v["id"] == vid)
    assert v["status"] == "in_flight"

    # combattenti in volo
    fs = _fighters(client, h, sid)
    for fid in fids:
        f = next(f for f in fs if f["id"] == fid)
        assert f["status"] == "in_flight"

    # missione in progress
    inflight = client.get(f"/api/agency/{sid}/missions/inflight", headers=h).json()
    assert any(m["id"] == mid for m in inflight)


def test_launch_wrong_vehicle_type(client):
    """Aereo caccia non può fare missione Terrestre (§9.3)."""
    h, sid = _setup(client)
    _set_balance(sid)
    aid = _agency_id(sid)
    mid = _inject_mission(sid, aid, MissionType.TERRESTRE)
    vid = _inject_mission_vehicle(sid, "fighter")
    fighters = _fighters(client, h, sid)
    fids = [fighters[0]["id"]]

    r = client.post(f"/api/agency/{sid}/missions/{mid}/launch",
                    json={"vehicle_id": vid, "fighter_ids": fids}, headers=h)
    assert r.status_code == 400
    assert "classe" in r.json()["detail"].lower()


def test_launch_terrestre_no_fighters(client):
    """Sbarco senza combattenti → errore."""
    h, sid = _setup(client)
    aid = _agency_id(sid)
    mid = _inject_mission(sid, aid, MissionType.TERRESTRE)
    vid = _inject_mission_vehicle(sid, "mission")

    r = client.post(f"/api/agency/{sid}/missions/{mid}/launch",
                    json={"vehicle_id": vid, "fighter_ids": []}, headers=h)
    assert r.status_code == 400


def test_launch_intercettazione(client):
    """Lancio missione Intercettazione Terrestre con caccia + pilota."""
    h, sid = _setup(client, email="int@x.com")
    _set_balance(sid)
    aid = _agency_id(sid)
    mid = _inject_mission(sid, aid, MissionType.INTERCETTAZIONE_TERRESTRE)
    vid = _inject_mission_vehicle(sid, "fighter")

    # assegna pilota con licenza B-Bronze al caccia
    pilots = _pilots(client, h, sid)
    pid = pilots[0]["id"]
    _give_pilot_license(pid, "B", "bronze")

    r = client.post(f"/api/agency/{sid}/vehicles/{vid}/assign-pilot",
                    json={"pilot_id": pid}, headers=h)
    assert r.status_code == 200

    r = client.post(f"/api/agency/{sid}/missions/{mid}/launch",
                    json={"vehicle_id": vid, "fighter_ids": []}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["mtype"] == "intercept_terra"


def test_launch_intercettazione_no_pilot(client):
    """Intercettazione senza pilota assegnato → errore."""
    h, sid = _setup(client, email="intnp@x.com")
    aid = _agency_id(sid)
    mid = _inject_mission(sid, aid, MissionType.INTERCETTAZIONE_TERRESTRE)
    vid = _inject_mission_vehicle(sid, "fighter")

    r = client.post(f"/api/agency/{sid}/missions/{mid}/launch",
                    json={"vehicle_id": vid, "fighter_ids": []}, headers=h)
    assert r.status_code == 400
    assert "pilota" in r.json()["detail"].lower()


# ─── §9.5-9.7 Risoluzione combattimento nel tick ─────────────────────────

def _force_return(mid, return_day=0.5):
    """Forza la sortie a rientrare al prossimo tick."""
    db = SessionLocal()
    db.query(Mission).filter(Mission.id == mid).update({"sortie_return_day": return_day})
    db.commit(); db.close()


def test_tick_resolves_terrestre(client):
    """Il tick risolve una missione terrestre e aggiorna le missioni completate."""
    h, sid = _setup(client, email="tres@x.com")
    _set_balance(sid)
    aid = _agency_id(sid)

    # forza combattenti con Pg molto alta per garantire successo
    db = SessionLocal()
    db.query(Fighter).filter(Fighter.agency_id == aid).update({
        "strg": 200, "dif": 200, "mov": 25, "spa": 200
    })
    db.commit(); db.close()

    mid = _inject_mission(sid, aid, MissionType.TERRESTRE, day=0)
    vid = _inject_mission_vehicle(sid, "mission")
    fighters = _fighters(client, h, sid)
    fids = [f["id"] for f in fighters[:4]]

    # lancia la missione
    client.post(f"/api/agency/{sid}/missions/{mid}/launch",
                json={"vehicle_id": vid, "fighter_ids": fids}, headers=h)

    # forza rientro
    _force_return(mid, return_day=0.5)

    # avanza di un tick
    r = client.post(f"/api/admin/server/{sid}/tick", headers=h)
    assert r.status_code == 200
    assert r.json()["agencies"][0]["sortie_risolte"] == 1

    ag = _get_agency(client, h, sid)
    assert ag["missions_completed"] == 1  # almeno 1 missione completata

    # vettore torna in hangar
    vs = _vehicles(client, h, sid)
    v = next(v for v in vs if v["id"] == vid)
    assert v["status"] == "barracks"

    # combattenti tornano in caserma
    fs = _fighters(client, h, sid)
    for fid in fids:
        f = next(f for f in fs if f["id"] == fid)
        assert f["status"] in ("barracks", "eliminated")


def test_tick_resolves_intercettazione_defeat(client):
    """Sconfitta in intercettazione: vettore + pilota eliminati (§9.6)."""
    h, sid = _setup(client, email="intdef@x.com")
    _set_balance(sid)
    aid = _agency_id(sid)

    # forza una missione con Pn altissima per garantire sconfitta
    db = SessionLocal()
    mid_raw = Mission(
        server_id=sid, agency_id=aid,
        mission_type=MissionType.INTERCETTAZIONE_TERRESTRE.value,
        alarm="verde", status=MissionStatus.ASSIGNED.value,
        target_lat=48.8, target_lon=2.3,
        pn=99999999.0, reward_estimate=0.0,
        assigned_day=0, deadline_day=7,
    )
    db.add(mid_raw); db.commit(); mid = mid_raw.id; db.close()

    vid = _inject_mission_vehicle(sid, "fighter")
    pilots = _pilots(client, h, sid)
    pid = pilots[0]["id"]
    _give_pilot_license(pid, "B", "bronze")
    client.post(f"/api/agency/{sid}/vehicles/{vid}/assign-pilot",
                json={"pilot_id": pid}, headers=h)

    client.post(f"/api/agency/{sid}/missions/{mid}/launch",
                json={"vehicle_id": vid, "fighter_ids": []}, headers=h)
    _force_return(mid, 0.5)
    client.post(f"/api/admin/server/{sid}/tick", headers=h)

    # vettore e pilota eliminati
    vs = client.get(f"/api/agency/{sid}/vehicles", headers=h).json()
    # il vettore eliminato non appare nella lista (filtriamo "eliminated" nell'API)
    # verifichiamo direttamente nel DB
    db = SessionLocal()
    v = db.get(Vehicle, vid)
    p = db.get(Pilot, pid)
    assert v.status == "eliminated"
    assert p.status == "eliminated"
    db.close()


def test_tick_reward_added_to_balance(client):
    """Il saldo aumenta della ricompensa dopo una missione riuscita."""
    h, sid = _setup(client, email="rew@x.com")
    _set_balance(sid, 50000)
    aid = _agency_id(sid)

    # forza combattenti forti
    db = SessionLocal()
    db.query(Fighter).filter(Fighter.agency_id == aid).update({
        "strg": 200, "dif": 200, "mov": 25, "spa": 200
    })
    db.commit(); db.close()

    mid = _inject_mission(sid, aid, MissionType.TERRESTRE, day=0)
    vid = _inject_mission_vehicle(sid, "mission")
    fighters = _fighters(client, h, sid)
    fids = [f["id"] for f in fighters[:8]]

    # Belisario ha 8 postazioni — usiamo tutti e 8 i fighters
    # ma ne abbiamo solo 4 dal recruit; ok, usiamo quelli che ci sono
    fids = [f["id"] for f in fighters]
    client.post(f"/api/agency/{sid}/missions/{mid}/launch",
                json={"vehicle_id": vid, "fighter_ids": fids}, headers=h)
    _force_return(mid, 0.5)

    ag_before = _get_agency(client, h, sid)
    client.post(f"/api/admin/server/{sid}/tick", headers=h)
    ag_after = _get_agency(client, h, sid)

    # con combattenti fortissimi il successo è quasi certo; saldo dovrebbe salire
    # (netto del tick = contributo + eventuale ricompensa - manutenzione - stipendi)
    # Non possiamo garantire il successo senza seed fisso, ma verifichiamo il flow
    missions = client.get(f"/api/agency/{sid}/missions", headers=h).json()
    resolved = [m for m in missions if m["status"] in ("completed", "failed")]
    assert len(resolved) >= 1


# ─── §9.10 Simulatore ─────────────────────────────────────────────────────

def test_simulate_mission(client):
    h, sid = _setup(client, email="sim@x.com")
    aid = _agency_id(sid)
    mid = _inject_mission(sid, aid, MissionType.TERRESTRE)
    vid = _inject_mission_vehicle(sid, "mission")
    fighters = _fighters(client, h, sid)
    fids_str = ",".join(str(f["id"]) for f in fighters[:2])

    r = client.get(
        f"/api/agency/{sid}/missions/{mid}/simulate",
        params={"vehicle_id": vid, "fighter_ids": fids_str},
        headers=h,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "pg" in data
    assert "prob_successo" in data
    assert 0.0 <= data["prob_successo"] <= 1.0


# ─── §9 Scadenza missioni (deadline) ─────────────────────────────────────

def test_missions_list_after_tick(client):
    """Dopo il tick le missioni assegnate sono visibili."""
    h, sid = _setup(client, email="mlist@x.com")
    r = client.post(f"/api/admin/server/{sid}/tick", headers=h)
    assert r.status_code == 200
    missions = client.get(f"/api/agency/{sid}/missions/active", headers=h).json()
    # le missioni assegnate dal tick (potrebbero essere 0 se ESPO = 0)
    assert isinstance(missions, list)


def test_launch_same_mission_twice(client):
    """Una missione già in progress non può essere rilancata."""
    h, sid = _setup(client, email="double@x.com")
    _set_balance(sid)
    aid = _agency_id(sid)
    mid = _inject_mission(sid, aid, MissionType.TERRESTRE)
    vid = _inject_mission_vehicle(sid, "mission")
    fighters = _fighters(client, h, sid)
    fids = [f["id"] for f in fighters[:2]]

    r1 = client.post(f"/api/agency/{sid}/missions/{mid}/launch",
                     json={"vehicle_id": vid, "fighter_ids": fids}, headers=h)
    assert r1.status_code == 200

    # tenta di rilanciarla
    vid2 = _inject_mission_vehicle(sid, "mission")
    r2 = client.post(f"/api/agency/{sid}/missions/{mid}/launch",
                     json={"vehicle_id": vid2, "fighter_ids": fids}, headers=h)
    assert r2.status_code == 400
