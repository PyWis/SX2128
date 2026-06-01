"""Test F4 — Teatri completi: allarmi, esplorazione, evacuazione, sortie catena, lunare."""
from app.database import SessionLocal
from app.gamedata import balance as B
from app.gamedata.enums import AlarmLevel, MissionStatus, MissionType
from app.models.core import Agency, Fighter, Mission, Pilot, Vehicle


# ─── helpers ────────────────────────────────────────────────────────────────

def _auth(client, email):
    r = client.post("/api/auth/register", json={"email": email, "password": "secret1"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup(client, email, culture="europea"):
    h = _auth(client, email)
    sid = client.post("/api/admin/server", json={"name": "F4"}, headers=h).json()["id"]
    client.post("/api/agency", json={
        "server_id": sid, "name": "F4 Agency", "culture": culture,
        "base_lat": 41.9, "base_lon": 12.5,
    }, headers=h)
    client.post(f"/api/agency/{sid}/recruit",
                json={"option": "pilota_4_combattenti"}, headers=h)
    return h, sid


def _set_balance(sid, amount=200000):
    db = SessionLocal()
    db.query(Agency).filter(Agency.server_id == sid).update({"balance": amount})
    db.commit(); db.close()


def _agency_id(sid):
    db = SessionLocal()
    ag = db.query(Agency).filter(Agency.server_id == sid).first()
    aid = ag.id; db.close(); return aid


def _get_agency(client, h, sid):
    return client.get(f"/api/agency/{sid}", headers=h).json()


def _fighters(client, h, sid):
    return client.get(f"/api/agency/{sid}/fighters", headers=h).json()


def _vehicles(client, h, sid):
    return client.get(f"/api/agency/{sid}/vehicles", headers=h).json()


def _inject_mission(sid, aid, mtype=MissionType.TERRESTRE, day=0, alarm="verde",
                    target_lat=48.8, target_lon=2.3, civili=None):
    from app.gamedata.enums import AlarmLevel as AL
    from app.services.formulas import enemy_power, reward as calc_reward
    db = SessionLocal()
    if mtype == MissionType.EVACUAZIONE:
        from app.services.formulas import enemy_index
        et = enemy_index(day)
        civili_count = civili if civili is not None else int(et * B.K_CIVILI_EVACUAZIONE)
        m = Mission(
            server_id=sid, agency_id=aid, mission_type=mtype.value,
            alarm=alarm, status=MissionStatus.ASSIGNED.value,
            target_lat=target_lat, target_lon=target_lon,
            pn=0.0, reward_estimate=civili_count * B.EVACUAZIONE_TARIFF,
            assigned_day=day, deadline_day=day + B.ALARM_VERDE_DAYS,
            civili_da_salvare=civili_count,
        )
    else:
        pn = enemy_power(mtype, day, n_combattenti=8)
        m = Mission(
            server_id=sid, agency_id=aid, mission_type=mtype.value,
            alarm=alarm, status=MissionStatus.ASSIGNED.value,
            target_lat=target_lat, target_lon=target_lon,
            pn=pn, reward_estimate=calc_reward(pn, mtype, AL.VERDE),
            assigned_day=day, deadline_day=day + B.ALARM_VERDE_DAYS,
        )
    db.add(m); db.commit(); mid = m.id; db.close(); return mid


def _inject_vehicle(sid, vclass="mission", project=None):
    """Aggiunge direttamente nel DB un vettore adatto al tipo missione."""
    project_map = {
        "mission": "Belisario", "fighter": "Tikal", "exploration": "Dubai",
        "space_mission": "Antares", "space_fighter": "Cygnus", "civilian": "Americo",
    }
    p = project or project_map[vclass]
    db = SessionLocal()
    ag = db.query(Agency).filter(Agency.server_id == sid).first()
    v = Vehicle(agency_id=ag.id, project=p, vclass=vclass, status="barracks")
    db.add(v); db.commit(); vid = v.id; db.close(); return vid


def _give_pilot_license(pilot_id, lic_type, tier):
    db = SessionLocal()
    p = db.get(Pilot, pilot_id)
    p.licenses = {**p.licenses, lic_type: tier}
    db.commit(); db.close()


def _force_return(mission_id, return_day=0.5):
    db = SessionLocal()
    db.query(Mission).filter(Mission.id == mission_id).update({"sortie_return_day": return_day})
    db.commit(); db.close()


def _set_last_login_recent(sid):
    from datetime import timezone, timedelta
    from app.models.core import utcnow
    db = SessionLocal()
    db.query(Agency).filter(Agency.server_id == sid).update({"last_login": utcnow()})
    db.commit(); db.close()


# ─── §9.2 Escalation allarmi ────────────────────────────────────────────────

def test_alarm_verde_to_giallo(client):
    """Missione Verde con scadenza passata → Giallo nel tick."""
    h, sid = _setup(client, "alarm1@x.com")
    aid = _agency_id(sid)
    mid = _inject_mission(sid, aid, MissionType.TERRESTRE, day=0)

    # imposta deadline già passata al giorno corrente
    db = SessionLocal()
    db.query(Mission).filter(Mission.id == mid).update({"deadline_day": 0, "assigned_day": 0})
    db.commit(); db.close()

    _set_last_login_recent(sid)
    client.post(f"/api/admin/server/{sid}/tick", headers=h)

    db = SessionLocal()
    m = db.get(Mission, mid)
    assert m.alarm == AlarmLevel.GIALLO.value, m.alarm
    db.close()


def test_alarm_giallo_to_rosso(client):
    """Missione Giallo con scadenza passata → Rosso nel tick."""
    h, sid = _setup(client, "alarm2@x.com")
    aid = _agency_id(sid)
    mid = _inject_mission(sid, aid, MissionType.TERRESTRE, day=0, alarm="giallo")

    db = SessionLocal()
    db.query(Mission).filter(Mission.id == mid).update({"deadline_day": 0, "assigned_day": 0})
    db.commit(); db.close()

    _set_last_login_recent(sid)
    client.post(f"/api/admin/server/{sid}/tick", headers=h)

    db = SessionLocal()
    m = db.get(Mission, mid)
    assert m.alarm == AlarmLevel.ROSSO.value
    db.close()


def test_alarm_rosso_ug_resolves(client):
    """Missione Rosso con scadenza passata → UG risolve (FAILED) nel tick."""
    h, sid = _setup(client, "alarm3@x.com")
    aid = _agency_id(sid)
    mid = _inject_mission(sid, aid, MissionType.TERRESTRE, day=0, alarm="rosso")

    db = SessionLocal()
    db.query(Mission).filter(Mission.id == mid).update({"deadline_day": 0, "assigned_day": 0})
    db.commit(); db.close()

    _set_last_login_recent(sid)
    r = client.post(f"/api/admin/server/{sid}/tick", headers=h)
    assert r.status_code == 200
    assert r.json()["ug_resolved"] >= 1

    db = SessionLocal()
    m = db.get(Mission, mid)
    assert m.status == MissionStatus.FAILED.value
    db.close()


# ─── §8.1 ESPO aeroplani da esplorazione ────────────────────────────────────

def test_espo_from_exploration(client):
    """Aeroplano da esplorazione in hangar con pilota genera ESPO nel tick."""
    h, sid = _setup(client, "espo1@x.com")
    _set_last_login_recent(sid)
    _set_balance(sid)

    # aggiunge un aeroplano da esplorazione e assegna il pilota
    vid = _inject_vehicle(sid, "exploration", "Dubai")
    pilots = client.get(f"/api/agency/{sid}/pilots", headers=h).json()
    pid = pilots[0]["id"]
    _give_pilot_license(pid, "A", "bronze")
    client.post(f"/api/agency/{sid}/vehicles/{vid}/assign-pilot",
                json={"pilot_id": pid}, headers=h)

    ag_before = _get_agency(client, h, sid)
    espo_before = ag_before["espo_today"]

    client.post(f"/api/admin/server/{sid}/tick", headers=h)
    ag_after = _get_agency(client, h, sid)

    assert ag_after["espo_today"] > espo_before


# ─── §9.9 Evacuazione civili ────────────────────────────────────────────────

def test_evacuazione_launch(client):
    """Lancio missione EVACUAZIONE con veicolo CIVILIAN."""
    h, sid = _setup(client, "evac1@x.com")
    _set_balance(sid, 5000000)
    aid = _agency_id(sid)
    mid = _inject_mission(sid, aid, MissionType.EVACUAZIONE, civili=5000)
    vid = _inject_vehicle(sid, "civilian", "Americo")

    r = client.post(f"/api/agency/{sid}/missions/{mid}/launch",
                    json={"vehicle_id": vid, "fighter_ids": []}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["mtype"] == MissionType.EVACUAZIONE.value


def test_evacuazione_wrong_vehicle(client):
    """EVACUAZIONE con vettore non CIVILIAN → errore."""
    h, sid = _setup(client, "evac2@x.com")
    _set_balance(sid)
    aid = _agency_id(sid)
    mid = _inject_mission(sid, aid, MissionType.EVACUAZIONE, civili=5000)
    vid = _inject_vehicle(sid, "mission", "Belisario")

    r = client.post(f"/api/agency/{sid}/missions/{mid}/launch",
                    json={"vehicle_id": vid, "fighter_ids": []}, headers=h)
    assert r.status_code == 400


def test_evacuazione_resolves_in_tick(client):
    """Evacuazione si risolve nel tick: civili salvati = min(cap, richiesti)."""
    h, sid = _setup(client, "evac3@x.com")
    _set_balance(sid, 5000000)
    _set_last_login_recent(sid)
    aid = _agency_id(sid)
    civili = 5000
    mid = _inject_mission(sid, aid, MissionType.EVACUAZIONE, civili=civili)
    vid = _inject_vehicle(sid, "civilian", "Americo")  # cap 10000 >= 5000

    client.post(f"/api/agency/{sid}/missions/{mid}/launch",
                json={"vehicle_id": vid, "fighter_ids": []}, headers=h)
    _force_return(mid, 0.5)
    client.post(f"/api/admin/server/{sid}/tick", headers=h)

    db = SessionLocal()
    m = db.get(Mission, mid)
    assert m.status == MissionStatus.COMPLETED.value
    assert m.resolution_json["civili_salvati"] == civili
    assert m.resolution_json["success"] is True
    db.close()

    ag = _get_agency(client, h, sid)
    assert ag["missions_completed"] >= 1


def test_evacuazione_capped_by_capacity(client):
    """Evacuazione con più civili della capacità → salvati = capacità del vettore."""
    h, sid = _setup(client, "evac4@x.com")
    _set_balance(sid, 5000000)
    _set_last_login_recent(sid)
    aid = _agency_id(sid)
    civili = 50000  # Americo cap è 10000
    mid = _inject_mission(sid, aid, MissionType.EVACUAZIONE, civili=civili)
    vid = _inject_vehicle(sid, "civilian", "Americo")

    client.post(f"/api/agency/{sid}/missions/{mid}/launch",
                json={"vehicle_id": vid, "fighter_ids": []}, headers=h)
    _force_return(mid, 0.5)
    client.post(f"/api/admin/server/{sid}/tick", headers=h)

    db = SessionLocal()
    m = db.get(Mission, mid)
    assert m.resolution_json["civili_salvati"] == 10000  # capped at Americo
    db.close()


# ─── §8.5 Transito lunare ────────────────────────────────────────────────────

def test_lunar_transit_adds_days(client):
    """Missione INTERCETTAZIONE_LUNARE ha ETA >= terrestre + LUNAR_TRANSIT_DAYS."""
    h, sid = _setup(client, "luna1@x.com")
    _set_balance(sid, 500000)
    aid = _agency_id(sid)

    mid_terra = _inject_mission(sid, aid, MissionType.INTERCETTAZIONE_TERRESTRE)
    mid_luna = _inject_mission(sid, aid, MissionType.INTERCETTAZIONE_LUNARE)

    # Tikal: B-Bronze; Cygnus: B-Silver (e D-Bronze)
    vid_fighter = _inject_vehicle(sid, "fighter", "Tikal")
    vid_space = _inject_vehicle(sid, "space_fighter", "Cygnus")

    pilots = client.get(f"/api/agency/{sid}/pilots", headers=h).json()
    pid = pilots[0]["id"]
    _give_pilot_license(pid, "B", "bronze")
    client.post(f"/api/agency/{sid}/vehicles/{vid_fighter}/assign-pilot",
                json={"pilot_id": pid}, headers=h)

    # secondo pilota per Cygnus (richiede B-Silver + D-Bronze): iniettato direttamente
    db = SessionLocal()
    ag = db.query(Agency).filter(Agency.server_id == sid).first()
    p2 = Pilot(agency_id=ag.id, name="Cosmo", origin_culture="europea",
               status="barracks", licenses={"B": "silver", "D": "bronze"})
    db.add(p2); db.commit(); pid2 = p2.id; db.close()
    client.post(f"/api/agency/{sid}/vehicles/{vid_space}/assign-pilot",
                json={"pilot_id": pid2}, headers=h)

    r_terra = client.post(f"/api/agency/{sid}/missions/{mid_terra}/launch",
                          json={"vehicle_id": vid_fighter, "fighter_ids": []}, headers=h)
    r_luna = client.post(f"/api/agency/{sid}/missions/{mid_luna}/launch",
                         json={"vehicle_id": vid_space, "fighter_ids": []}, headers=h)
    assert r_terra.status_code == 200, r_terra.text
    assert r_luna.status_code == 200, r_luna.text

    eta_terra = r_terra.json()["eta_days"]
    eta_luna = r_luna.json()["eta_days"]
    assert r_luna.json()["is_space"] is True
    assert eta_luna >= eta_terra + B.LUNAR_TRANSIT_DAYS - 0.5


# ─── §9.11 Sortie multi-missione ────────────────────────────────────────────

def test_chain_launch(client):
    """Lancio catena di 2 missioni terrestri sullo stesso vettore."""
    h, sid = _setup(client, "chain1@x.com")
    _set_balance(sid)
    aid = _agency_id(sid)

    mid1 = _inject_mission(sid, aid, MissionType.TERRESTRE, target_lat=35.7, target_lon=139.7)
    mid2 = _inject_mission(sid, aid, MissionType.TERRESTRE, target_lat=-33.9, target_lon=151.2)
    vid = _inject_vehicle(sid, "mission", "Belisario")
    fighters = _fighters(client, h, sid)
    fids = [f["id"] for f in fighters[:4]]

    r = client.post(f"/api/agency/{sid}/missions/{mid1}/launch",
                    json={
                        "vehicle_id": vid,
                        "fighter_ids": fids,
                        "chain_legs": [{"mission_id": mid2, "fighter_ids": fids[:2]}],
                    }, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["chain_legs"] == 1

    # entrambe le missioni devono essere IN_PROGRESS
    db = SessionLocal()
    m1 = db.get(Mission, mid1)
    m2 = db.get(Mission, mid2)
    assert m1.status == MissionStatus.IN_PROGRESS.value
    assert m2.status == MissionStatus.IN_PROGRESS.value
    assert m1.chain_leg == 0
    assert m2.chain_leg == 1
    assert m1.sortie_return_day == m2.sortie_return_day  # stesso ETA
    db.close()


def test_chain_eta_longer_than_single(client):
    """ETA catena > ETA singola missione (path base→Tokyo→Sydney→base vs base→Tokyo→base)."""
    # Usa target lontani dalla base (Roma 41.9,12.5) per uscire dal floor di 1.0g
    TOKYO = {"target_lat": 35.7, "target_lon": 139.7}
    SYDNEY = {"target_lat": -33.9, "target_lon": 151.2}

    h, sid = _setup(client, "chain2@x.com")
    _set_balance(sid)
    aid = _agency_id(sid)

    mid_solo = _inject_mission(sid, aid, MissionType.TERRESTRE, **TOKYO)
    vid_solo = _inject_vehicle(sid, "mission", "Belisario")
    fighters = _fighters(client, h, sid)
    fids = [f["id"] for f in fighters[:2]]
    r_solo = client.post(f"/api/agency/{sid}/missions/{mid_solo}/launch",
                         json={"vehicle_id": vid_solo, "fighter_ids": fids}, headers=h)
    assert r_solo.status_code == 200

    h2, sid2 = _setup(client, "chain2b@x.com")
    _set_balance(sid2)
    aid2 = _agency_id(sid2)
    mid1 = _inject_mission(sid2, aid2, MissionType.TERRESTRE, **TOKYO)
    mid2 = _inject_mission(sid2, aid2, MissionType.TERRESTRE, **SYDNEY)
    vid2 = _inject_vehicle(sid2, "mission", "Belisario")
    f2 = _fighters(client, h2, sid2)
    fids2 = [f["id"] for f in f2[:2]]

    r_chain = client.post(f"/api/agency/{sid2}/missions/{mid1}/launch",
                          json={"vehicle_id": vid2, "fighter_ids": fids2,
                                "chain_legs": [{"mission_id": mid2, "fighter_ids": fids2}]},
                          headers=h2)
    assert r_chain.status_code == 200
    assert r_chain.json()["eta_days"] > r_solo.json()["eta_days"]


def test_chain_max_legs_exceeded(client):
    """Catena con più di CHAIN_MAX_LEGS tappe → errore."""
    h, sid = _setup(client, "chain3@x.com")
    _set_balance(sid)
    aid = _agency_id(sid)

    missions = [_inject_mission(sid, aid, MissionType.TERRESTRE) for _ in range(B.CHAIN_MAX_LEGS + 1)]
    vid = _inject_vehicle(sid, "mission", "Belisario")
    fighters = _fighters(client, h, sid)
    fids = [f["id"] for f in fighters[:2]]

    chain = [{"mission_id": m, "fighter_ids": fids} for m in missions[1:]]  # 4 tappe aggiuntive
    r = client.post(f"/api/agency/{sid}/missions/{missions[0]}/launch",
                    json={"vehicle_id": vid, "fighter_ids": fids, "chain_legs": chain},
                    headers=h)
    assert r.status_code == 400


def test_chain_resolves_in_tick(client):
    """Il tick risolve entrambe le missioni della catena."""
    h, sid = _setup(client, "chain4@x.com")
    _set_balance(sid)
    _set_last_login_recent(sid)
    aid = _agency_id(sid)

    # potenzia i combattenti per garantire successo
    db = SessionLocal()
    db.query(Fighter).filter(Fighter.agency_id == aid).update(
        {"strg": 200, "dif": 200, "mov": 25, "spa": 200}
    )
    db.commit(); db.close()

    mid1 = _inject_mission(sid, aid, MissionType.TERRESTRE, target_lat=48.8, target_lon=2.3)
    mid2 = _inject_mission(sid, aid, MissionType.TERRESTRE, target_lat=51.5, target_lon=0.1)
    vid = _inject_vehicle(sid, "mission", "Belisario")
    fighters = _fighters(client, h, sid)
    fids = [f["id"] for f in fighters]

    r = client.post(f"/api/agency/{sid}/missions/{mid1}/launch",
                    json={"vehicle_id": vid, "fighter_ids": fids,
                          "chain_legs": [{"mission_id": mid2, "fighter_ids": fids}]},
                    headers=h)
    assert r.status_code == 200

    # forza rientro
    db = SessionLocal()
    db.query(Mission).filter(Mission.id.in_([mid1, mid2])).update({"sortie_return_day": 0.5})
    db.commit(); db.close()

    r_tick = client.post(f"/api/admin/server/{sid}/tick", headers=h)
    assert r_tick.status_code == 200
    assert r_tick.json()["agencies"][0]["sortie_risolte"] >= 2

    db = SessionLocal()
    m1 = db.get(Mission, mid1)
    m2 = db.get(Mission, mid2)
    assert m1.status in (MissionStatus.COMPLETED.value, MissionStatus.FAILED.value)
    assert m2.status in (MissionStatus.COMPLETED.value, MissionStatus.FAILED.value)
    v = db.get(Vehicle, vid)
    assert v.status == "barracks"
    db.close()


# ─── §9.3 Date di sblocco ────────────────────────────────────────────────────

def test_unlock_dates_intercettazione(client):
    """Prima del giorno 45 non vengono assegnate missioni di intercettazione."""
    from app.services.missions import _unlocked_types
    assert MissionType.TERRESTRE in _unlocked_types(0)
    assert MissionType.INTERCETTAZIONE_TERRESTRE not in _unlocked_types(0)
    assert MissionType.INTERCETTAZIONE_TERRESTRE in _unlocked_types(45)
    assert MissionType.INTERCETTAZIONE_LUNARE not in _unlocked_types(45)
    assert MissionType.INTERCETTAZIONE_LUNARE in _unlocked_types(92)
    assert MissionType.LUNARE in _unlocked_types(123)
    assert MissionType.EVACUAZIONE in _unlocked_types(50)
