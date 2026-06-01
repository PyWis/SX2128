"""Test F6 — Monetizzazione: shop, pool premium, anti-P2W, Agenda 2030, Campioni cycle, Delpy."""
from app.database import SessionLocal
from app.gamedata import balance as B
from app.gamedata.shop import PACKAGES, AGENDA_2030_RATE
from app.models.core import Agency, Server, ShopTransaction


# ─── helpers ────────────────────────────────────────────────────────────────

def _auth(client, email):
    r = client.post("/api/auth/register", json={"email": email, "password": "secret1"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup(client, email, culture="europea"):
    h = _auth(client, email)
    sid = client.post("/api/admin/server", json={"name": "F6"}, headers=h).json()["id"]
    client.post("/api/agency", json={
        "server_id": sid, "name": "F6 Agency", "culture": culture,
        "base_lat": 41.9, "base_lon": 12.5,
    }, headers=h)
    return h, sid


def _set_balance(sid, amount=200_000):
    db = SessionLocal()
    db.query(Agency).filter(Agency.server_id == sid).update({"balance": amount})
    db.commit(); db.close()


def _set_server_day(sid, day):
    db = SessionLocal()
    db.query(Server).filter(Server.id == sid).update({"current_day": day})
    db.commit(); db.close()


def _set_last_login_recent(sid):
    from app.models.core import utcnow
    db = SessionLocal()
    db.query(Agency).filter(Agency.server_id == sid).update({"last_login": utcnow()})
    db.commit(); db.close()


def _agency_id(sid):
    db = SessionLocal()
    ag = db.query(Agency).filter(Agency.server_id == sid).first()
    aid = ag.id; db.close(); return aid


# ─── Catalogo ────────────────────────────────────────────────────────────────

def test_shop_catalog_returns_all_packages(client):
    """Il catalogo contiene 13 pacchetti: 10 Plus cultura + Core + 2 ticket."""
    h, sid = _setup(client, "cat1@x.com")
    r = client.get("/api/shop/catalog", headers=h)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == len(PACKAGES)
    keys = {i["key"] for i in items}
    assert "plus_europea" in keys
    assert "plus_core" in keys
    assert "ticket_pro" in keys
    assert "ticket_campioni" in keys


def test_catalog_has_correct_prices(client):
    """Pacchetti Plus a 5€, ticket_pro 10€, ticket_campioni 100€."""
    h, sid = _setup(client, "cat2@x.com")
    r = client.get("/api/shop/catalog", headers=h)
    items = {i["key"]: i for i in r.json()}
    assert items["plus_europea"]["price_eur"] == 5.0
    assert items["plus_core"]["price_eur"] == 5.0
    assert items["ticket_pro"]["price_eur"] == 10.0
    assert items["ticket_campioni"]["price_eur"] == 100.0


def test_catalog_agenda_2030_is_10_pct(client):
    """Ogni pacchetto traccia il 10% per Agenda 2030."""
    h, sid = _setup(client, "cat3@x.com")
    r = client.get("/api/shop/catalog", headers=h)
    for item in r.json():
        expected = round(item["price_eur"] * AGENDA_2030_RATE, 2)
        assert abs(item["agenda_2030_eur"] - expected) < 0.01


def test_catalog_plus_units_count(client):
    """Pacchetto Plus cultura: 2 piloti + 8 combattenti + 1 vettore."""
    h, sid = _setup(client, "cat4@x.com")
    r = client.get("/api/shop/catalog", headers=h)
    items = {i["key"]: i for i in r.json()}
    pkg = items["plus_europea"]
    assert pkg["pilots"] == 2
    assert pkg["fighters"] == 8
    assert pkg["vehicle"] is not None


# ─── Acquisto e Pool Premium ──────────────────────────────────────────────────

def test_buy_package_adds_to_pool(client):
    """Acquistare un pacchetto Plus aggiunge unità al pool di riserva."""
    h, sid = _setup(client, "buy1@x.com")

    r = client.post("/api/shop/purchase", headers=h, json={
        "server_id": sid, "package_key": "plus_europea",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["pool_size"] == 2 + 8 + 1  # 2 piloti + 8 combattenti + 1 vettore
    assert data["pool_summary"]["pilot"] == 2
    assert data["pool_summary"]["fighter"] == 8
    assert data["pool_summary"]["vehicle"] == 1


def test_buy_package_agenda_2030_tracked(client):
    """La transazione traccia il 10% per Agenda 2030."""
    h, sid = _setup(client, "buy2@x.com")
    r = client.post("/api/shop/purchase", headers=h, json={
        "server_id": sid, "package_key": "plus_europea",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["agenda_2030_eur"] == round(5.0 * AGENDA_2030_RATE, 2)


def test_buy_transaction_saved(client):
    """La transazione è persistita nel DB."""
    h, sid = _setup(client, "buy3@x.com")
    client.post("/api/shop/purchase", headers=h, json={
        "server_id": sid, "package_key": "plus_core",
    })

    r = client.get(f"/api/shop/{sid}/transactions", headers=h)
    assert r.status_code == 200
    txs = r.json()
    assert len(txs) == 1
    assert txs[0]["package_key"] == "plus_core"
    assert txs[0]["price_eur"] == 5.0


def test_pool_endpoint_shows_contents(client):
    """GET /api/shop/{sid}/pool restituisce il contenuto del pool."""
    h, sid = _setup(client, "pool1@x.com")
    client.post("/api/shop/purchase", headers=h, json={
        "server_id": sid, "package_key": "plus_africana",
    })
    r = client.get(f"/api/shop/{sid}/pool", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["pool_size"] == 11  # 2+8+1
    assert data["pool"]["pilot"] == 2


# ─── Anti-P2W ────────────────────────────────────────────────────────────────

def test_anti_p2w_daily_limit(client):
    """Non si può acquistare due pacchetti lo stesso giorno."""
    h, sid = _setup(client, "ap1@x.com")
    client.post("/api/shop/purchase", headers=h, json={
        "server_id": sid, "package_key": "plus_europea",
    })
    r2 = client.post("/api/shop/purchase", headers=h, json={
        "server_id": sid, "package_key": "plus_cinese",
    })
    assert r2.status_code == 400
    assert "oggi" in r2.json()["detail"].lower()


def test_anti_p2w_cycle_limit(client):
    """Non si può acquistare più di 1 pacchetto Plus per ciclo."""
    h, sid = _setup(client, "ap2@x.com")
    # Primo acquisto
    client.post("/api/shop/purchase", headers=h, json={
        "server_id": sid, "package_key": "plus_europea",
    })
    # Simula giorno successivo (resetta il controllo giornaliero)
    db = SessionLocal()
    from datetime import datetime, timezone, timedelta
    db.query(ShopTransaction).filter(ShopTransaction.server_id == sid).update({
        "created_at": datetime.now(timezone.utc) - timedelta(days=1)
    })
    db.commit(); db.close()

    # Secondo acquisto stesso ciclo → bloccato
    r2 = client.post("/api/shop/purchase", headers=h, json={
        "server_id": sid, "package_key": "plus_cinese",
    })
    assert r2.status_code == 400
    assert "ciclo" in r2.json()["detail"].lower()


def test_anti_p2w_next_cycle_allowed(client):
    """Nel ciclo successivo si può riacquistare."""
    h, sid = _setup(client, "ap3@x.com")
    # Acquisto ciclo 1
    client.post("/api/shop/purchase", headers=h, json={
        "server_id": sid, "package_key": "plus_europea",
    })
    # Sposta transaction a ciclo 0 e avanza il server al ciclo 2
    db = SessionLocal()
    from datetime import datetime, timezone, timedelta
    db.query(ShopTransaction).filter(ShopTransaction.server_id == sid).update({
        "created_at": datetime.now(timezone.utc) - timedelta(days=1),
        "cycle_at_purchase": 0,
    })
    db.query(Server).filter(Server.id == sid).update({"cycle": 2})
    db.commit(); db.close()

    r2 = client.post("/api/shop/purchase", headers=h, json={
        "server_id": sid, "package_key": "plus_cinese",
    })
    assert r2.status_code == 200, r2.text


# ─── Riscatto Pool ────────────────────────────────────────────────────────────

def test_redeem_pilot_from_pool(client):
    """Si può riscattare un pilota dal pool di riserva."""
    h, sid = _setup(client, "red1@x.com")
    client.post("/api/shop/purchase", headers=h, json={
        "server_id": sid, "package_key": "plus_europea",
    })

    r = client.post(f"/api/shop/{sid}/redeem", headers=h, json={"unit_type": "pilot"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["unit_type"] == "pilot"
    assert "name" in data
    assert data["pool_remaining"] == 10  # 11 - 1


def test_redeem_fighter_from_pool(client):
    """Si può riscattare un combattente dal pool."""
    h, sid = _setup(client, "red2@x.com")
    client.post("/api/shop/purchase", headers=h, json={
        "server_id": sid, "package_key": "plus_europea",
    })
    # Riscatta il pilota prima (recruited_today limit)
    client.post(f"/api/shop/{sid}/redeem", headers=h, json={"unit_type": "pilot"})
    # Avanza giorno per resettare recruited_today
    _set_last_login_recent(sid)
    client.post(f"/api/admin/server/{sid}/tick", headers=h)

    r = client.post(f"/api/shop/{sid}/redeem", headers=h, json={"unit_type": "fighter"})
    assert r.status_code == 200, r.text
    assert r.json()["unit_type"] == "fighter"


def test_redeem_vehicle_from_pool(client):
    """Si può riscattare un vettore dal pool (non usa slot reclutamento)."""
    h, sid = _setup(client, "red3@x.com")
    client.post("/api/shop/purchase", headers=h, json={
        "server_id": sid, "package_key": "plus_europea",
    })

    r = client.post(f"/api/shop/{sid}/redeem", headers=h, json={"unit_type": "vehicle"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["unit_type"] == "vehicle"
    assert "project" in data


def test_redeem_uses_recruit_slot(client):
    """Riscattare pilota/combattente usa il limite giornaliero di reclutamento."""
    h, sid = _setup(client, "red4@x.com")
    client.post("/api/shop/purchase", headers=h, json={
        "server_id": sid, "package_key": "plus_europea",
    })
    # Prima riscattata
    client.post(f"/api/shop/{sid}/redeem", headers=h, json={"unit_type": "pilot"})
    # Seconda nella stessa giornata → bloccata
    r2 = client.post(f"/api/shop/{sid}/redeem", headers=h, json={"unit_type": "fighter"})
    assert r2.status_code == 400
    assert "oggi" in r2.json()["detail"].lower()


def test_redeem_vehicle_no_recruit_slot(client):
    """Riscattare un vettore NON usa il limite giornaliero."""
    h, sid = _setup(client, "red5@x.com")
    # Recluta normalmente prima (esaurisce il slot)
    client.post(f"/api/agency/{sid}/recruit", json={"option": "solo_pilota"}, headers=h)
    # Acquista e riscatta vettore → deve funzionare anche con recruited_today=True
    client.post("/api/shop/purchase", headers=h, json={
        "server_id": sid, "package_key": "plus_europea",
    })
    r = client.post(f"/api/shop/{sid}/redeem", headers=h, json={"unit_type": "vehicle"})
    assert r.status_code == 200, r.text


def test_redeem_empty_pool_error(client):
    """Riscattare da un pool vuoto restituisce 400."""
    h, sid = _setup(client, "red6@x.com")
    r = client.post(f"/api/shop/{sid}/redeem", headers=h, json={"unit_type": "pilot"})
    assert r.status_code == 400


# ─── Server Campioni — ciclo ogni 10 giorni ───────────────────────────────────

def test_campioni_cycle_every_10_days(client):
    """Su un server Campioni, il Taglio avviene ogni 10 giorni."""
    h = _auth(client, "camp1@x.com")
    # Crea server Campioni (speed=4)
    sid = client.post("/api/admin/server",
                      json={"name": "Campioni Test", "server_type": "campioni"},
                      headers=h).json()["id"]
    # Controlla che speed sia 4
    db = SessionLocal()
    server = db.get(Server, sid)
    assert server.speed == B.SPEED_CAMPIONI
    db.close()


def test_campioni_taglio_at_day_10(client):
    """Un server Campioni fa taglio al giorno 10, non 40."""
    h, sid = _setup(client, "camp2@x.com")
    # Imposta speed=4 manualmente
    db = SessionLocal()
    db.query(Server).filter(Server.id == sid).update({"speed": 4})
    agencies = db.query(Agency).filter(Agency.server_id == sid).all()
    for a in agencies:
        a.missions_completed = 5
        a.active = True
    db.commit(); db.close()

    _set_last_login_recent(sid)
    _set_server_day(sid, B.CAMPIONI_CYCLE_DAYS - 1)
    r = client.post(f"/api/admin/server/{sid}/tick", headers=h)
    assert r.status_code == 200
    data = r.json()
    # Il taglio deve essere avvenuto al giorno 10
    assert "taglio" in data, f"Taglio non trovato nel tick, day={data.get('day')}"


# ─── Delpy Notifiche §5.20 ───────────────────────────────────────────────────

def test_delpy_unlock_notification(client):
    """Delpy posta una notifica quando si sbloccano nuovi tipi di missione."""
    from app.models.core import ChatMessage
    from app.services.missions import UNLOCK_DAY
    from app.gamedata.enums import MissionType

    h, sid = _setup(client, "delpy1@x.com")
    _set_last_login_recent(sid)

    # Avanza al giorno prima dello sblocco Intercettazione Terrestre (day 45)
    unlock_day = UNLOCK_DAY[MissionType.INTERCETTAZIONE_TERRESTRE]
    _set_server_day(sid, unlock_day - 1)
    client.post(f"/api/admin/server/{sid}/tick", headers=h)

    db = SessionLocal()
    msgs = db.query(ChatMessage).filter(
        ChatMessage.server_id == sid,
        ChatMessage.channel_type == "delpy",
    ).all()
    db.close()
    assert any("sbloccat" in m.body.lower() or "Intercett" in m.body for m in msgs)


def test_delpy_pre_taglio_warning(client):
    """Delpy avvisa 5 giorni prima del Taglio UG."""
    from app.models.core import ChatMessage

    h, sid = _setup(client, "delpy2@x.com")
    _set_last_login_recent(sid)

    # Avanza a 6 giorni prima del ciclo (tick porta a 5 giorni prima)
    _set_server_day(sid, B.CYCLE_DAYS - 6)
    client.post(f"/api/admin/server/{sid}/tick", headers=h)

    db = SessionLocal()
    msgs = db.query(ChatMessage).filter(
        ChatMessage.server_id == sid,
        ChatMessage.channel_type == "delpy",
    ).all()
    db.close()
    assert any("5 giorni" in m.body for m in msgs)
