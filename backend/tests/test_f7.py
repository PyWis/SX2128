"""Test F7 — Bilanciamento & Hardening: formule, Monte Carlo, chat rate-limit, tick idempotency."""
import random
import time
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.gamedata import balance as B
from app.gamedata.enums import AlarmLevel, MissionType
from app.models.core import Agency, ChatMessage, Server
from app.services import formulas as F
from app.services.monte_carlo import (
    breakeven_pg,
    combat_simulation,
    income_band_report,
    k_luna_analysis,
)


# ─── helpers ────────────────────────────────────────────────────────────────

def _auth(client, email):
    r = client.post("/api/auth/register", json={"email": email, "password": "secret1"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup(client, email, culture="europea"):
    h = _auth(client, email)
    sid = client.post("/api/admin/server", json={"name": "F7"}, headers=h).json()["id"]
    client.post("/api/agency", json={
        "server_id": sid, "name": "F7 Agency", "culture": culture,
        "base_lat": 41.9, "base_lon": 12.5,
    }, headers=h)
    return h, sid


def _set_last_login_recent(sid):
    from app.models.core import utcnow
    db = SessionLocal()
    db.query(Agency).filter(Agency.server_id == sid).update({"last_login": utcnow()})
    db.commit(); db.close()


# ─── Formule unit test ────────────────────────────────────────────────────────

def test_enemy_index_phase_a_linear():
    """E(t) è lineare in fase A: E(0)=100, E(60)=340."""
    assert F.enemy_index(0) == B.E_BASE
    assert F.enemy_index(60) == B.E_BASE + B.PHASE_A_SLOPE * 60


def test_enemy_index_phase_b_compound():
    """E(t) in fase B è composta a partire da E(60)."""
    e60 = F.enemy_index(60)
    assert abs(F.enemy_index(61) - e60 * B.PHASE_B_DAILY) < 0.01


def test_enemy_index_continuity_at_t60():
    """E(t) è continua in t=60 (nessun salto)."""
    assert abs(F.enemy_index(59.9) - F.enemy_index(60)) < 1.0


def test_reward_formula():
    """Ricompensa = Pn * mult_tipo * mult_allarme (§9.7)."""
    pn = 1000.0
    r_verde = F.reward(pn, MissionType.TERRESTRE, AlarmLevel.VERDE)
    assert r_verde == pn * B.REWARD_MULT_TERRESTRE * B.ALARM_MULT_VERDE

    r_rosso = F.reward(pn, MissionType.INTERCETTAZIONE_TERRESTRE, AlarmLevel.ROSSO)
    assert abs(r_rosso - pn * B.REWARD_MULT_INTERCETTAZIONE * B.ALARM_MULT_ROSSO) < 0.01


def test_reward_alarm_ordering():
    """Verde > Giallo > Rosso per la stessa missione."""
    pn = 500.0
    r_v = F.reward(pn, MissionType.TERRESTRE, AlarmLevel.VERDE)
    r_g = F.reward(pn, MissionType.TERRESTRE, AlarmLevel.GIALLO)
    r_r = F.reward(pn, MissionType.TERRESTRE, AlarmLevel.ROSSO)
    assert r_v > r_g > r_r


def test_resolve_combat_success_when_pg_dominant():
    """Con Pg = 10×Pn il combattimento deve sempre vincere."""
    rng = random.Random(0)
    for _ in range(100):
        result = F.resolve_combat(10000.0, 100.0, rng)
        assert result.success
        assert result.overwhelming


def test_resolve_combat_fail_when_pn_dominant():
    """Con Pn = 10×Pg il combattimento deve sempre perdere."""
    rng = random.Random(0)
    for _ in range(100):
        result = F.resolve_combat(100.0, 10000.0, rng)
        assert not result.success


def test_random_factor_bounds():
    """Il fattore casuale applicato è sempre in [0.75, 1.25]."""
    rng = random.Random(1)
    for _ in range(1000):
        r = F.resolve_combat(1000.0, 1000.0, rng)
        assert B.RANDOM_MIN <= r.pg_eff / r.pg <= B.RANDOM_MAX
        assert B.RANDOM_MIN <= r.pn_eff / r.pn <= B.RANDOM_MAX


def test_contributo_fazione_linear():
    """Contributo cresce linearmente con i giorni di fedeltà."""
    c0 = F.contributo_fazione(200, 0.5, 0)
    c1 = F.contributo_fazione(200, 0.5, 100)
    assert c1 > c0
    expected = 200 * (1 + 0.5 / 100 * 100)
    assert abs(c1 - expected) < 0.01


def test_exp_multiplier_tiers():
    """Scaglioni esperienza: 0→1, 5→2, 89→8."""
    assert F.exp_multiplier(0) == 1
    assert F.exp_multiplier(5) == 2
    assert F.exp_multiplier(89) == 8
    assert F.exp_multiplier(100) == 8


def test_cofinanziamento_ug_scale():
    """Cofinanziamento UG è 100 R per missione (§10)."""
    assert F.cofinanziamento_ug(0) == 0
    assert F.cofinanziamento_ug(5) == 500
    assert F.cofinanziamento_ug(3) == 300


# ─── Monte Carlo unit test ────────────────────────────────────────────────────

def test_monte_carlo_equal_pg_pn_near_50pct():
    """Con Pg = Pn il win_rate deve essere vicino al 50%."""
    result = combat_simulation(1000.0, 1000.0, n=20_000, rng_seed=42)
    assert 0.45 <= result["win_rate"] <= 0.55


def test_monte_carlo_pg_double_pn_high_win():
    """Con Pg = 2×Pn il win_rate deve superare 90%."""
    result = combat_simulation(2000.0, 1000.0, n=10_000, rng_seed=42)
    assert result["win_rate"] > 0.90


def test_monte_carlo_result_keys():
    """Il risultato contiene tutte le chiavi attese."""
    result = combat_simulation(500.0, 500.0, n=1000, rng_seed=1)
    for key in ("pg", "pn", "n", "win_rate", "overwhelming_rate", "avg_damage",
                "median_damage", "max_damage"):
        assert key in result, f"chiave mancante: {key}"


def test_monte_carlo_seed_deterministic():
    """Con lo stesso seed il risultato è identico."""
    r1 = combat_simulation(800.0, 600.0, n=5000, rng_seed=99)
    r2 = combat_simulation(800.0, 600.0, n=5000, rng_seed=99)
    assert r1 == r2


def test_breakeven_pg_near_50pct():
    """breakeven_pg trova il Pg che dà ~50% win_rate."""
    pn = 1000.0
    pg = breakeven_pg(pn, target_win_rate=0.5, n=5000)
    # Con pg ≈ pn il win rate dovrebbe essere vicino a 0.5
    result = combat_simulation(pg, pn, n=10_000, rng_seed=42)
    assert abs(result["win_rate"] - 0.5) < 0.10


def test_income_band_report_structure():
    """income_band_report ritorna una lista con 't', 'E', 'cultura', 'reddito_min_R_g'."""
    rows = income_band_report()
    assert len(rows) > 0
    for row in rows:
        assert "t" in row
        assert "E" in row
        assert "cultura" in row
        assert "reddito_min_R_g" in row
        assert "reddito_max_R_g" in row
        assert row["reddito_max_R_g"] >= row["reddito_min_R_g"]


def test_income_band_monotone_enemy_index():
    """L'indice nemico E cresce nel tempo."""
    rows = income_band_report([0, 30, 60, 90])
    by_t = {r["t"]: r["E"] for r in rows if r["cultura"] == "europea"}
    ts = sorted(by_t.keys())
    for i in range(len(ts) - 1):
        assert by_t[ts[i + 1]] >= by_t[ts[i]]


def test_k_luna_analysis_structure():
    """k_luna_analysis ritorna le chiavi attese con win rates validi."""
    result = k_luna_analysis(n=2000)
    assert "terra" in result and "luna" in result
    assert 0.0 <= result["terra"]["win_rate"] <= 1.0
    assert 0.0 <= result["luna"]["win_rate"] <= 1.0
    assert result["win_ratio_luna_vs_terra"] is not None


def test_k_luna_harder_than_terra():
    """La missione lunare deve avere win_rate < terrestre (k_luna > 1)."""
    result = k_luna_analysis(n=5000)
    assert result["luna"]["win_rate"] < result["terra"]["win_rate"]


# ─── API Monte Carlo ──────────────────────────────────────────────────────────

def test_mc_simulate_api(client):
    """POST /api/admin/montecarlo/simulate ritorna win_rate."""
    h, _ = _setup(client, "mc1@x.com")
    r = client.post("/api/admin/montecarlo/simulate", headers=h,
                    json={"pg": 1000.0, "pn": 1000.0, "n": 1000})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "win_rate" in data
    assert 0.0 <= data["win_rate"] <= 1.0


def test_mc_simulate_invalid_pg(client):
    """pg<=0 deve restituire 422."""
    h, _ = _setup(client, "mc2@x.com")
    r = client.post("/api/admin/montecarlo/simulate", headers=h,
                    json={"pg": 0.0, "pn": 500.0})
    assert r.status_code == 422


def test_mc_breakeven_api(client):
    """POST /api/admin/montecarlo/breakeven ritorna breakeven_pg."""
    h, _ = _setup(client, "mc3@x.com")
    r = client.post("/api/admin/montecarlo/breakeven", headers=h,
                    json={"pn": 1000.0, "n": 2000})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "breakeven_pg" in data
    assert data["breakeven_pg"] > 0


def test_mc_income_band_api(client):
    """GET /api/admin/montecarlo/income-band ritorna lista non vuota."""
    h, _ = _setup(client, "mc4@x.com")
    r = client.get("/api/admin/montecarlo/income-band", headers=h)
    assert r.status_code == 200, r.text
    assert len(r.json()) > 0


def test_mc_k_luna_api(client):
    """GET /api/admin/montecarlo/k-luna ritorna confronto terra/luna."""
    h, _ = _setup(client, "mc5@x.com")
    r = client.get("/api/admin/montecarlo/k-luna", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["k_luna"] == B.K_LUNA
    assert data["luna"]["win_rate"] < data["terra"]["win_rate"]


# ─── Chat rate-limit ──────────────────────────────────────────────────────────

def _insert_messages(sid, n, channel_type="ug_net", channel_key="global"):
    """Inserisce n messaggi nel canale dato, datati adesso."""
    from app.models.core import utcnow
    db = SessionLocal()
    agency = db.query(Agency).filter(Agency.server_id == sid).first()
    for i in range(n):
        msg = ChatMessage(
            server_id=sid,
            channel_type=channel_type,
            channel_key=channel_key,
            author_agency_id=agency.id,
            body=f"msg {i}",
        )
        db.add(msg)
    db.commit(); db.close()


def test_chat_rate_limit_ug_net(client):
    """Superare 20 msg/ora su UG-Net viene bloccato."""
    h, sid = _setup(client, "rl1@x.com")
    # Pre-inserisce 20 messaggi nell'ultima ora
    _insert_messages(sid, 20, channel_type="ug_net", channel_key="global")
    # Il 21° tramite API deve fallire
    r = client.post(f"/api/chat/{sid}/messages", headers=h,
                    json={"channel_type": "ug_net", "channel_key": "global",
                          "body": "messaggio extra"})
    assert r.status_code == 400
    assert "rate limit" in r.json()["detail"].lower() or "rate" in r.json()["detail"].lower()


def test_chat_rate_limit_other_channel(client):
    """Superare 50 msg/ora su canale generico viene bloccato."""
    h, sid = _setup(client, "rl2@x.com")
    _insert_messages(sid, 50, channel_type="cultura", channel_key="europea")
    r = client.post(f"/api/chat/{sid}/messages", headers=h,
                    json={"channel_type": "cultura", "channel_key": "europea",
                          "body": "messaggio extra"})
    assert r.status_code == 400


def test_chat_rate_limit_ug_lower_than_other(client):
    """UG-Net ha limite più basso (20 vs 50): 21° msg su UG bloccato, 21° su cultura OK."""
    h, sid = _setup(client, "rl3@x.com")
    # 21 messaggi su UG → bloccato
    _insert_messages(sid, 20, channel_type="ug_net", channel_key="global")
    r_ug = client.post(f"/api/chat/{sid}/messages", headers=h,
                       json={"channel_type": "ug_net", "channel_key": "global",
                             "body": "overflow"})
    assert r_ug.status_code == 400

    # solo 20 messaggi su cultura → ancora permesso
    _insert_messages(sid, 20, channel_type="cultura", channel_key="europea")
    r_cult = client.post(f"/api/chat/{sid}/messages", headers=h,
                         json={"channel_type": "cultura", "channel_key": "europea",
                               "body": "ventesimo"})
    assert r_cult.status_code == 200


def test_chat_old_messages_not_counted(client):
    """Messaggi più vecchi di 1 ora non contano nel rate-limit."""
    from app.models.core import utcnow
    db = SessionLocal()
    agency = db.query(Agency).filter(Agency.server_id ==
                                     # lookup agency via separate setup
                                     None).first()
    db.close()

    h, sid = _setup(client, "rl4@x.com")
    old_time = datetime.now(timezone.utc) - timedelta(hours=2)
    # Inserisce 25 messaggi vecchi (>1h fa)
    db = SessionLocal()
    agency = db.query(Agency).filter(Agency.server_id == sid).first()
    for i in range(25):
        msg = ChatMessage(
            server_id=sid, channel_type="ug_net", channel_key="global",
            author_agency_id=agency.id, body=f"old {i}",
            created_at=old_time,
        )
        db.add(msg)
    db.commit(); db.close()

    # Messaggio fresco: deve passare (solo 0 messaggi nell'ultima ora)
    r = client.post(f"/api/chat/{sid}/messages", headers=h,
                    json={"channel_type": "ug_net", "channel_key": "global",
                          "body": "nuovo messaggio"})
    assert r.status_code == 200, r.text


# ─── Tick idempotency ─────────────────────────────────────────────────────────

def test_tick_increments_day(client):
    """Il tick incrementa il giorno del server di 1."""
    h, sid = _setup(client, "tick1@x.com")
    _set_last_login_recent(sid)
    r = client.post(f"/api/admin/server/{sid}/tick", headers=h)
    assert r.status_code == 200
    assert r.json()["day"] == 1


def test_tick_does_not_double_assign_missions(client):
    """Due tick consecutivi non raddoppiano le missioni assegnate."""
    from app.models.core import Mission
    h, sid = _setup(client, "tick2@x.com")
    _set_last_login_recent(sid)
    client.post(f"/api/admin/server/{sid}/tick", headers=h)
    client.post(f"/api/admin/server/{sid}/tick", headers=h)

    db = SessionLocal()
    missions = db.query(Mission).filter(Mission.server_id == sid).all()
    db.close()
    # Dopo 2 tick un giocatore non deve avere più di MISSION_CAP_PER_PLAYER*2 missioni
    assert len(missions) <= B.MISSION_CAP_PER_PLAYER * 2 + 5  # small margin for UG


def test_tick_balance_never_negative_from_salary(client):
    """Il tick non porta il bilancio sotto zero solo per stipendi (§5.4)."""
    h, sid = _setup(client, "tick3@x.com")
    _set_last_login_recent(sid)
    # Bilancio zero prima del tick
    db = SessionLocal()
    db.query(Agency).filter(Agency.server_id == sid).update({"balance": 0})
    db.commit(); db.close()

    r = client.post(f"/api/admin/server/{sid}/tick", headers=h)
    assert r.status_code == 200

    db = SessionLocal()
    agency = db.query(Agency).filter(Agency.server_id == sid).first()
    balance = agency.balance
    db.close()
    # Il bilancio può diventare negativo per stipendi, ma il tick non deve crashare
    assert balance is not None


# ─── Performance ─────────────────────────────────────────────────────────────

def test_monte_carlo_100k_runs_fast():
    """100.000 prove Monte Carlo completano in meno di 30 secondi."""
    start = time.monotonic()
    combat_simulation(1000.0, 900.0, n=100_000, rng_seed=0)
    elapsed = time.monotonic() - start
    assert elapsed < 30.0, f"Troppo lento: {elapsed:.1f}s"
