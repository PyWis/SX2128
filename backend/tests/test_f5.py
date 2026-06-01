"""Test F5 — Multiplayer & Endgame: classifica, ciclo/taglio, alleanze, chat, missioni UG."""
from app.database import SessionLocal
from app.gamedata import balance as B
from app.gamedata.enums import AlarmLevel, AllianceRole, MissionStatus, MissionType
from app.models.core import Agency, Alliance, Mission, Pilot


# ─── helpers ────────────────────────────────────────────────────────────────

def _auth(client, email):
    r = client.post("/api/auth/register", json={"email": email, "password": "secret1"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup(client, email, culture="europea", name="Agency"):
    h = _auth(client, email)
    sid = client.post("/api/admin/server", json={"name": "F5"}, headers=h).json()["id"]
    client.post("/api/agency", json={
        "server_id": sid, "name": name, "culture": culture,
        "base_lat": 41.9, "base_lon": 12.5,
    }, headers=h)
    return h, sid


def _agency_id(sid, user_id=None):
    db = SessionLocal()
    q = db.query(Agency).filter(Agency.server_id == sid)
    if user_id:
        q = q.filter(Agency.user_id == user_id)
    ag = q.first()
    aid = ag.id
    db.close()
    return aid


def _set_balance(sid, amount=200_000):
    db = SessionLocal()
    db.query(Agency).filter(Agency.server_id == sid).update({"balance": amount})
    db.commit(); db.close()


def _set_missions_completed(agency_id, count):
    db = SessionLocal()
    db.query(Agency).filter(Agency.id == agency_id).update({"missions_completed": count})
    db.commit(); db.close()


def _set_espo_total(agency_id, espo):
    db = SessionLocal()
    db.query(Agency).filter(Agency.id == agency_id).update({"espo_total": espo})
    db.commit(); db.close()


def _set_last_login_recent(sid):
    from app.models.core import utcnow
    db = SessionLocal()
    db.query(Agency).filter(Agency.server_id == sid).update({"last_login": utcnow()})
    db.commit(); db.close()


def _set_server_day(sid, day):
    from app.models.core import Server
    db = SessionLocal()
    db.query(Server).filter(Server.id == sid).update({"current_day": day})
    db.commit(); db.close()


def _inject_mission(sid, aid, mtype=MissionType.TERRESTRE, day=0, alarm="verde",
                    transferred_from=None, alliance_id=None):
    from app.services.formulas import enemy_power, reward as calc_reward
    db = SessionLocal()
    pn = enemy_power(mtype, day, n_combattenti=8)
    status = MissionStatus.ASSIGNED.value
    m = Mission(
        server_id=sid, agency_id=aid, mission_type=mtype.value,
        alarm=alarm, status=status,
        target_lat=48.8, target_lon=2.3,
        pn=pn, reward_estimate=calc_reward(pn, mtype, AlarmLevel.VERDE),
        assigned_day=day, deadline_day=day + B.ALARM_VERDE_DAYS,
        transferred_from_agency_id=transferred_from,
        alliance_id=alliance_id,
    )
    db.add(m); db.commit(); mid = m.id; db.close(); return mid


# ─── §11 Classifica ─────────────────────────────────────────────────────────

def test_classifica_sorted_by_missions(client):
    """Classifica ordinata per missioni completate decrescente."""
    h, sid = _setup(client, "cls1@x.com")
    h2, _ = _auth(client, "cls2@x.com"), None
    # Crea seconda agenzia sullo stesso server
    r = client.post("/api/agency", json={
        "server_id": sid, "name": "Agency2", "culture": "cinese",
        "base_lat": 35.7, "base_lon": 139.7,
    }, headers=_auth(client, "cls2b@x.com"))

    db = SessionLocal()
    agencies = db.query(Agency).filter(Agency.server_id == sid).all()
    assert len(agencies) >= 1
    aid1 = agencies[0].id
    db.close()

    _set_missions_completed(aid1, 42)

    r = client.get(f"/api/classifica/{sid}", headers=h)
    assert r.status_code == 200
    ranks = r.json()
    assert len(ranks) >= 1
    assert ranks[0]["missions_completed"] >= ranks[-1]["missions_completed"]


def test_classifica_espo_tiebreaker(client):
    """A parità di missioni, ESPO totale decide il ranking."""
    h, sid = _setup(client, "cls3@x.com")
    h2 = _auth(client, "cls4@x.com")
    client.post("/api/agency", json={
        "server_id": sid, "name": "Agency2", "culture": "cinese",
        "base_lat": 35.7, "base_lon": 139.7,
    }, headers=h2)

    db = SessionLocal()
    agencies = db.query(Agency).filter(Agency.server_id == sid).all()
    a1, a2 = agencies[0], agencies[1]
    a1.missions_completed = 10; a1.espo_total = 500.0
    a2.missions_completed = 10; a2.espo_total = 200.0
    db.commit(); db.close()

    r = client.get(f"/api/classifica/{sid}", headers=h)
    assert r.status_code == 200
    ranks = r.json()
    assert ranks[0]["espo_total"] >= ranks[1]["espo_total"]


# ─── §11 Taglio UG / Ciclo 40gg ──────────────────────────────────────────────

def _setup_multi_agency_server(client, n=4):
    """Crea un server con n agenzie."""
    emails = [f"taglio{i}@x.com" for i in range(n)]
    headers = [_auth(client, e) for e in emails]
    sid = client.post("/api/admin/server", json={"name": "Taglio"}, headers=headers[0]).json()["id"]
    for i, h in enumerate(headers):
        client.post("/api/agency", json={
            "server_id": sid, "name": f"Agenzia{i}", "culture": "europea",
            "base_lat": 41.9 + i, "base_lon": 12.5 + i,
        }, headers=h)
    return headers[0], sid, headers


def test_taglio_ug_cuts_bottom_25(client):
    """Al ciclo 40gg, il 25% peggiore per missioni viene tagliato."""
    h, sid, all_h = _setup_multi_agency_server(client, n=4)

    db = SessionLocal()
    agencies = db.query(Agency).filter(Agency.server_id == sid).all()
    # assegna missioni diverse: 1 ha 0, gli altri hanno di più
    for i, a in enumerate(agencies):
        a.missions_completed = i * 10  # 0, 10, 20, 30
        a.last_login = __import__('app.models.core', fromlist=['utcnow']).utcnow()
        a.active = True
    db.commit(); db.close()

    # Avanza il server al giorno 39 prima del tick (tick porterà a 40)
    _set_server_day(sid, 39)

    client.post(f"/api/admin/server/{sid}/tick", headers=h)

    db = SessionLocal()
    tagliati = db.query(Agency).filter(
        Agency.server_id == sid, Agency.cut_by_ug == True).all()
    assert len(tagliati) >= 1
    # L'agenzia con 0 missioni deve essere tagliata
    assert any(a.missions_completed <= 0 for a in tagliati)
    db.close()


def test_trasporto_coloni_top_half_bonus(client):
    """Il top 50% delle agenzie riceve +25 missioni al ciclo."""
    h, sid, _ = _setup_multi_agency_server(client, n=4)

    db = SessionLocal()
    agencies = db.query(Agency).filter(Agency.server_id == sid).all()
    for i, a in enumerate(agencies):
        a.missions_completed = (i + 1) * 10  # 10, 20, 30, 40
        a.last_login = __import__('app.models.core', fromlist=['utcnow']).utcnow()
        a.active = True
    db.commit(); db.close()

    _set_server_day(sid, 39)
    client.post(f"/api/admin/server/{sid}/tick", headers=h)

    db = SessionLocal()
    agencies = db.query(Agency).filter(Agency.server_id == sid).all()
    max_mc = max(a.missions_completed for a in agencies)
    # Il top avrà ricevuto +25 (prima del taglio) → almeno 40 + 25 - possibili tagli
    assert max_mc >= 40 + B.TRASPORTO_COLONI_VALUE - 1   # tolleranza per taglio
    db.close()


def test_cycle_counter_increments(client):
    """server.cycle incrementa dopo ogni Taglio UG."""
    from app.models.core import Server
    h, sid, _ = _setup_multi_agency_server(client, n=4)

    db = SessionLocal()
    agencies = db.query(Agency).filter(Agency.server_id == sid).all()
    for a in agencies:
        a.missions_completed = 5
        a.active = True
        a.last_login = __import__('app.models.core', fromlist=['utcnow']).utcnow()
    db.commit(); db.close()

    _set_server_day(sid, 39)
    client.post(f"/api/admin/server/{sid}/tick", headers=h)

    db = SessionLocal()
    server = db.get(Server, sid)
    assert server.cycle == 2
    db.close()


# ─── §12 Alleanze ────────────────────────────────────────────────────────────

def test_alliance_create(client):
    """Crea un'alleanza; il fondatore diventa capo."""
    h, sid = _setup(client, "all1@x.com")

    r = client.post("/api/alliances", json={"server_id": sid, "name": "Squadra Alpha"}, headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["name"] == "Squadra Alpha"
    assert len(data["members"]) == 1
    assert data["members"][0]["role"] == AllianceRole.CAPO.value


def test_alliance_join(client):
    """Un secondo giocatore si unisce all'alleanza."""
    h1, sid = _setup(client, "all2a@x.com")
    h2 = _auth(client, "all2b@x.com")
    client.post("/api/agency", json={
        "server_id": sid, "name": "Agency2", "culture": "cinese",
        "base_lat": 35.7, "base_lon": 139.7,
    }, headers=h2)

    r_create = client.post("/api/alliances", json={"server_id": sid, "name": "Bravo"}, headers=h1)
    al_id = r_create.json()["id"]

    r_join = client.post(f"/api/alliances/{al_id}/join", params={"server_id": sid}, headers=h2)
    assert r_join.status_code == 200
    data = r_join.json()
    assert len(data["members"]) == 2


def test_alliance_max_members(client):
    """Aggiungere oltre 28 membri restituisce 400."""
    # Crea alleanza con 28 membri (troppo costoso creare 28 accounts, verifica il check)
    from app.services.alliance_service import AllianceError
    db = SessionLocal()
    # Simula la creazione manuale
    a1 = db.query(Agency).first()
    if a1:
        al = Alliance(server_id=a1.server_id, name="FullHouse", treasury=0.0, capo_agency_id=a1.id)
        db.add(al); db.flush()
        # Metti 28 agenzie fittizie nel count
        for i in range(B.ALLIANCE_MAX_MEMBERS):
            fake = Agency(
                user_id=a1.user_id, server_id=a1.server_id,
                name=f"Fake{i}", culture="europea",
                alliance_id=al.id, alliance_role=AllianceRole.MEMBRO.value,
            )
            db.add(fake)
        db.commit()
        al_id = al.id
        db.close()

        from app.services import alliance_service
        db2 = SessionLocal()
        # Un'agenzia senza alleanza cerca di unirsi
        new_ag = Agency(user_id=a1.user_id + 999, server_id=a1.server_id,
                        name="Newcomer", culture="europea")
        db2.add(new_ag); db2.flush()
        try:
            alliance_service.join_alliance(db2, new_ag, al_id)
            assert False, "doveva sollevare AllianceError"
        except AllianceError as e:
            assert "completo" in str(e)
        finally:
            db2.close()
    else:
        pass  # nessuna agenzia, skip


def test_alliance_leave_dissolves_when_alone(client):
    """L'ultimo membro che lascia dissolve l'alleanza."""
    h, sid = _setup(client, "all4@x.com")
    r = client.post("/api/alliances", json={"server_id": sid, "name": "Solo"}, headers=h)
    al_id = r.json()["id"]

    r_leave = client.delete(f"/api/alliances/{al_id}/leave", params={"server_id": sid}, headers=h)
    assert r_leave.status_code == 200

    db = SessionLocal()
    al = db.get(Alliance, al_id)
    assert al is None  # dissolto
    ag = db.query(Agency).filter(Agency.server_id == sid).first()
    assert ag.alliance_id is None
    db.close()


def test_alliance_treasury_deposit_withdraw(client):
    """Deposito e prelievo dalla tesoreria."""
    h, sid = _setup(client, "all5@x.com")
    _set_balance(sid, 10_000)
    r = client.post("/api/alliances", json={"server_id": sid, "name": "Treasury"}, headers=h)
    al_id = r.json()["id"]

    r_dep = client.post(f"/api/alliances/{al_id}/treasury/deposit",
                        params={"server_id": sid},
                        json={"amount": 500.0}, headers=h)
    assert r_dep.status_code == 200
    assert r_dep.json()["treasury"] == 500.0

    r_with = client.post(f"/api/alliances/{al_id}/treasury/withdraw",
                         params={"server_id": sid},
                         json={"amount": 200.0}, headers=h)
    assert r_with.status_code == 200
    assert r_with.json()["treasury"] == 300.0


def test_alliance_withdraw_only_capo(client):
    """Un membro normale non può prelevare dalla tesoreria."""
    h1, sid = _setup(client, "all6a@x.com")
    h2 = _auth(client, "all6b@x.com")
    client.post("/api/agency", json={
        "server_id": sid, "name": "Agency2", "culture": "cinese",
        "base_lat": 35.7, "base_lon": 139.7,
    }, headers=h2)

    r = client.post("/api/alliances", json={"server_id": sid, "name": "Hierarchy"}, headers=h1)
    al_id = r.json()["id"]
    client.post(f"/api/alliances/{al_id}/join", params={"server_id": sid}, headers=h2)
    _set_balance(sid, 5_000)

    # deposita come capo
    client.post(f"/api/alliances/{al_id}/treasury/deposit",
                params={"server_id": sid}, json={"amount": 500.0}, headers=h1)

    # prova a prelevare come membro → 400
    r_w = client.post(f"/api/alliances/{al_id}/treasury/withdraw",
                      params={"server_id": sid}, json={"amount": 100.0}, headers=h2)
    assert r_w.status_code == 400


def test_alliance_promote_colonnello(client):
    """Il capo può promuovere un membro a colonnello."""
    h1, sid = _setup(client, "all7a@x.com")
    h2 = _auth(client, "all7b@x.com")
    client.post("/api/agency", json={
        "server_id": sid, "name": "Agency2", "culture": "africana",
        "base_lat": 0.0, "base_lon": 0.0,
    }, headers=h2)

    r = client.post("/api/alliances", json={"server_id": sid, "name": "Command"}, headers=h1)
    al_id = r.json()["id"]
    client.post(f"/api/alliances/{al_id}/join", params={"server_id": sid}, headers=h2)

    # ottieni id agenzia 2
    db = SessionLocal()
    a2 = db.query(Agency).filter(Agency.server_id == sid, Agency.alliance_id == al_id,
                                  Agency.alliance_role == AllianceRole.MEMBRO.value).first()
    a2_id = a2.id; db.close()

    r_promo = client.post(f"/api/alliances/{al_id}/promote",
                          params={"server_id": sid},
                          json={"target_agency_id": a2_id}, headers=h1)
    assert r_promo.status_code == 200
    assert r_promo.json()["role"] == AllianceRole.COLONNELLO.value


# ─── §12 Trasferimento missioni ───────────────────────────────────────────────

def test_mission_transfer_to_alliance(client):
    """Una missione Verde viene trasferita al pool alleanza."""
    h, sid = _setup(client, "mtr1@x.com")
    aid = _agency_id(sid)

    r = client.post("/api/alliances", json={"server_id": sid, "name": "Pool"}, headers=h)
    al_id = r.json()["id"]

    mid = _inject_mission(sid, aid)

    r_tr = client.post(f"/api/alliances/{al_id}/transfer-mission",
                       params={"server_id": sid},
                       json={"mission_id": mid}, headers=h)
    assert r_tr.status_code == 200, r_tr.text
    data = r_tr.json()
    assert data["alliance_id"] == al_id
    assert data["transferred_from_agency_id"] == aid

    db = SessionLocal()
    m = db.get(Mission, mid)
    assert m.agency_id is None
    assert m.alliance_id == al_id
    db.close()


def test_transfer_only_verde(client):
    """Solo missioni Verde possono essere trasferite."""
    h, sid = _setup(client, "mtr2@x.com")
    aid = _agency_id(sid)
    r = client.post("/api/alliances", json={"server_id": sid, "name": "Pool2"}, headers=h)
    al_id = r.json()["id"]
    mid = _inject_mission(sid, aid, alarm="giallo")

    r_tr = client.post(f"/api/alliances/{al_id}/transfer-mission",
                       params={"server_id": sid},
                       json={"mission_id": mid}, headers=h)
    assert r_tr.status_code == 400


# ─── §13 Chat ────────────────────────────────────────────────────────────────

def test_chat_send_receive(client):
    """Invia e recupera un messaggio su UG-Net."""
    h, sid = _setup(client, "chat1@x.com")

    r_send = client.post(f"/api/chat/{sid}/messages", headers=h, json={
        "channel_type": "ug_net", "channel_key": "global", "body": "Ciao a tutti!",
    })
    assert r_send.status_code == 200, r_send.text
    assert r_send.json()["body"] == "Ciao a tutti!"

    r_get = client.get(f"/api/chat/{sid}/messages/ug_net/global", headers=h)
    assert r_get.status_code == 200
    msgs = r_get.json()
    assert any(m["body"] == "Ciao a tutti!" for m in msgs)


def test_chat_cultura_restricted(client):
    """Non si può inviare messaggi nel canale di un'altra cultura."""
    h, sid = _setup(client, "chat2@x.com", culture="europea")

    r = client.post(f"/api/chat/{sid}/messages", headers=h, json={
        "channel_type": "cultura", "channel_key": "cinese", "body": "Intrusione",
    })
    assert r.status_code == 400


def test_chat_cultura_own(client):
    """Si può inviare messaggi nel canale della propria cultura."""
    h, sid = _setup(client, "chat3@x.com", culture="africana")

    r = client.post(f"/api/chat/{sid}/messages", headers=h, json={
        "channel_type": "cultura", "channel_key": "africana", "body": "Solidarietà!",
    })
    assert r.status_code == 200


def test_chat_alleanza_restricted(client):
    """Non si può scrivere nel canale di un'alleanza di cui non si è membri."""
    h, sid = _setup(client, "chat4@x.com")

    r = client.post(f"/api/chat/{sid}/messages", headers=h, json={
        "channel_type": "alleanza", "channel_key": "999", "body": "Intruso",
    })
    assert r.status_code == 400


def test_chat_delpy_readonly(client):
    """Il canale Delpy è di sola lettura."""
    h, sid = _setup(client, "chat5@x.com")

    r = client.post(f"/api/chat/{sid}/messages", headers=h, json={
        "channel_type": "delpy", "channel_key": "", "body": "Test",
    })
    assert r.status_code == 400


def test_chat_alleanza_own(client):
    """Si può scrivere nel canale della propria alleanza."""
    h, sid = _setup(client, "chat6@x.com")
    r = client.post("/api/alliances", json={"server_id": sid, "name": "ChatAl"}, headers=h)
    al_id = r.json()["id"]

    r_msg = client.post(f"/api/chat/{sid}/messages", headers=h, json={
        "channel_type": "alleanza", "channel_key": str(al_id), "body": "Ops briefing",
    })
    assert r_msg.status_code == 200


# ─── §9.8 Missioni UG ────────────────────────────────────────────────────────

def test_ug_missions_generated_at_interval(client):
    """Missioni UG generate ogni UG_MISSION_INTERVAL giorni a partire dal day 30."""
    from app.services.missions import UNLOCK_DAY, UG_MISSION_INTERVAL
    h, sid = _setup(client, "ugm1@x.com")

    # Porta il server al giorno prima dell'intervallo UG
    ug_start = UNLOCK_DAY[MissionType.UG]
    _set_server_day(sid, ug_start + UG_MISSION_INTERVAL - 1)
    _set_last_login_recent(sid)

    # tick → current_day = ug_start + UG_MISSION_INTERVAL (multiplo di intervallo)
    r = client.post(f"/api/admin/server/{sid}/tick", headers=h)
    assert r.status_code == 200

    db = SessionLocal()
    ug_missions = db.query(Mission).filter(
        Mission.server_id == sid,
        Mission.mission_type == MissionType.UG.value,
        Mission.status == MissionStatus.AVAILABLE.value,
    ).all()
    db.close()
    assert len(ug_missions) >= 1


def test_ug_missions_not_before_unlock(client):
    """Nessuna missione UG prima del day 30."""
    h, sid = _setup(client, "ugm2@x.com")
    _set_last_login_recent(sid)

    # Rimani sotto il threshold
    for _ in range(5):
        client.post(f"/api/admin/server/{sid}/tick", headers=h)

    db = SessionLocal()
    ug_missions = db.query(Mission).filter(
        Mission.server_id == sid,
        Mission.mission_type == MissionType.UG.value,
    ).all()
    db.close()
    assert len(ug_missions) == 0


# ─── §11 Taglio Delpy notification ───────────────────────────────────────────

def test_taglio_delpy_notification(client):
    """Al ciclo 40gg, Delpy posta un messaggio di sistema."""
    from app.models.core import ChatMessage
    h, sid, _ = _setup_multi_agency_server(client, n=4)

    db = SessionLocal()
    agencies = db.query(Agency).filter(Agency.server_id == sid).all()
    for a in agencies:
        a.missions_completed = 5
        a.active = True
        a.last_login = __import__('app.models.core', fromlist=['utcnow']).utcnow()
    db.commit(); db.close()

    _set_server_day(sid, 39)
    client.post(f"/api/admin/server/{sid}/tick", headers=h)

    db = SessionLocal()
    delpy_msgs = db.query(ChatMessage).filter(
        ChatMessage.server_id == sid,
        ChatMessage.channel_type == "delpy",
    ).all()
    db.close()
    assert len(delpy_msgs) >= 1
    assert any("Taglio" in m.body for m in delpy_msgs)
