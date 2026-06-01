"""Test delle formule di gioco core (GDD §1, §3, §4, §9)."""
import math
import random

import pytest

from app.gamedata import balance as B
from app.gamedata.enums import AlarmLevel, MissionType
from app.services import formulas as F


# --- §1 fedelta lineare ---
def test_contributo_fedelta_lineare():
    # base 250, +3%/g, giorno 0 -> base
    assert F.contributo_fazione(250, 3.0, 0) == 250
    # giorno 10 -> 250 * (1 + 0.03*10) = 250 * 1.3 = 325
    assert F.contributo_fazione(250, 3.0, 10) == pytest.approx(325)


def test_continuita_curva_nemico_t60():
    # Fase A in t=60 = 340; Fase B parte da 340 (continua, §9.4)
    assert F.enemy_index(60) == pytest.approx(340)
    assert F.enemy_index(0) == 100
    # raddoppio ~ ogni 19 giorni in fase B
    assert F.enemy_index(80) > F.enemy_index(60)


def test_phase_b_compound_step():
    # +3.71%/g equivale a x1.2 ogni 5 giorni
    assert F.enemy_index(65) == pytest.approx(340 * 1.2, rel=0.02)


# --- §3.2 stat pilota ---
def test_pilot_stat_range_e_arrotondamento():
    rng = random.Random(0)
    for _ in range(1000):
        s = F.roll_pilot_stat(rng)
        assert 0 <= s <= 15
        assert (s * 2) == int(s * 2)  # multiplo di 0.5


def test_pilot_stars():
    assert F.pilot_stat_stars(15) == "quadrato_rosso"
    assert F.pilot_stat_stars(2.5) == "0_stelle"
    assert F.pilot_stat_stars(4) == "1_stelle"
    assert F.pilot_stat_stars(7) == "2_stelle"


# --- §3.3 stat combattente ---
def test_fighter_stats_range():
    rng = random.Random(1)
    for _ in range(1000):
        s = F.roll_fighter_stats(rng)
        assert s["VIT"] == 100
        assert 50 <= s["STR"] <= 100
        assert 50 <= s["DIF"] <= 100
        assert 5 <= s["MOV"] <= 20
        assert 0 <= s["SPA"] <= 100
        assert s["TABI"] == s["STR"] + s["DIF"] + s["MOV"] + s["SPA"]


# --- §4.5 stipendio ---
def test_stipendio_e_esperienza():
    assert F.exp_multiplier(0) == 1
    assert F.exp_multiplier(2) == 1
    assert F.exp_multiplier(5) == 2
    assert F.exp_multiplier(89) == 8
    # sqrt(1700)/5 * 1
    assert F.stipendio_combattente(1700, 0) == pytest.approx(math.sqrt(1700) / 5)


# --- §9.4 Pn ---
def test_enemy_power_planes():
    e0 = F.enemy_index(0)  # 100
    assert F.enemy_power(MissionType.TERRESTRE, 0, n_combattenti=8) == pytest.approx(8 * e0 * B.K_SBARCO)
    assert F.enemy_power(MissionType.INTERCETTAZIONE_TERRESTRE, 0) == pytest.approx(e0 * B.K_INT)
    assert F.enemy_power(MissionType.INTERCETTAZIONE_LUNARE, 0) == pytest.approx(e0 * B.K_INT * B.K_LUNA)


# --- §9.5 Pg / combattimento ---
def test_pg_intercettazione():
    # Tikal: attacco 100, vel 1.5; 4 missili bronze (+50 cad = 200); STR% 0
    pg = F.pg_intercettazione(100, 200, 0.0, 1.5)
    assert pg == pytest.approx(300 * (1 + 0.15))  # = 345


def test_resolve_combat_overwhelming_no_damage():
    rng = random.Random(42)
    r = F.resolve_combat(pg=1000, pn=100, rng=rng)
    assert r.success
    assert r.overwhelming
    assert r.danno_totale == 0


def test_resolve_combat_defeat_damage():
    rng = random.Random(42)
    r = F.resolve_combat(pg=10, pn=1000, rng=rng)
    assert not r.success
    assert r.danno_totale > 0


def test_ripartisci_danno_inverso_dif():
    # combattente con DIF alta incassa meno
    danni = F.ripartisci_danno(100, [50, 100])
    assert danni[0] > danni[1]
    assert sum(danni) == pytest.approx(100)


# --- §9.7 ricompensa ---
def test_reward_multipliers():
    pn = 100
    assert F.reward(pn, MissionType.TERRESTRE, AlarmLevel.VERDE) == pytest.approx(100)
    assert F.reward(pn, MissionType.INTERCETTAZIONE_TERRESTRE, AlarmLevel.VERDE) == pytest.approx(120)
    assert F.reward(pn, MissionType.LUNARE, AlarmLevel.VERDE) == pytest.approx(150)
    assert F.reward(pn, MissionType.TERRESTRE, AlarmLevel.ROSSO) == pytest.approx(50)


# --- §9.1 assegnazione ---
def test_missioni_giocatore_floor_e_cap():
    # floor: almeno 1 anche con 0 ESPO
    assert F.missioni_giocatore(100, 0, 0) == 1
    # cap a 11
    assert F.missioni_giocatore(1000, 100, 100) == 11
    # quota proporzionale
    assert F.missioni_giocatore(40, 25, 100) == 1 + int(40 * 25 / 100)  # 1+10=11 -> cap 11


# --- §8 tempo volo ---
def test_tempo_volo():
    assert F.tempo_volo_terrestre(3.0, 1.5) == 2.0
    with pytest.raises(ValueError):
        F.tempo_volo_terrestre(1.0, 0)


# --- §10 cofinanziamento ---
def test_cofinanziamento():
    assert F.cofinanziamento_ug(5) == 500
