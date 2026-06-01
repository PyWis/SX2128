"""Formule di gioco pure (deterministiche dove possibile) — GDD §1, §3, §4, §5, §9.

Tutte le funzioni qui sono prive di stato e di accesso al DB: prendono numeri,
restituiscono numeri. Sono il cuore testabile del motore di gioco.
Il generatore casuale e iniettabile per rendere i test deterministici.
"""
from __future__ import annotations

import math
import random as _random
from dataclasses import dataclass

from app.gamedata import balance as B
from app.gamedata.enums import MissionType, AlarmLevel

Rng = _random.Random


# ---------------------------------------------------------------------------
# §1 Governo — fedelta culturale (LINEARE con reset, §14)
# ---------------------------------------------------------------------------
def contributo_fazione(base_r: int, fedelta_pct_giorno: float, giorni_fedelta: int) -> float:
    """contributo = base * (1 + fedelta%/g * giorni_fedelta)."""
    return base_r * (1 + (fedelta_pct_giorno / 100.0) * giorni_fedelta)


# ---------------------------------------------------------------------------
# §3.2 Statistiche Pilota / §3.3 Combattente
# ---------------------------------------------------------------------------
def roll_pilot_stat(rng: Rng) -> float:
    """1% * rand(0,10) + 1% * rand(0,5) -> max 15%, arrotondato a 0.5."""
    val = rng.randint(0, 10) + rng.randint(0, 5)  # 0..15 (in punti percentuali)
    return round(val * 2) / 2.0  # arrotondamento alla mezza unita


def pilot_stat_stars(pct: float) -> str:
    """Rappresentazione a stelle (§3.2)."""
    if pct == 15:
        return "quadrato_rosso"
    if pct <= 2.5:
        return "0_stelle"
    # 3-5 -> 1 stella, 6-8 -> 2 stelle, ecc. (fasce da 3 a partire da 3%)
    return f"{int((pct - 3) // 3) + 1}_stelle"


def roll_fighter_stats(rng: Rng) -> dict[str, int]:
    """§3.3: VIT=100, STR/DIF=50-100, MOV=5-20, SPA=0-100, TABI=somma di STR+DIF+MOV+SPA."""
    str_ = 50 + 25 * rng.randint(0, 1) + 25 * rng.randint(0, 1)          # 50..100
    dif = 50 + 25 * rng.randint(0, 1) + 25 * rng.randint(0, 1)           # 50..100
    mov = 10 + 5 * rng.randint(0, 1) + 5 * rng.randint(-1, 1)            # 5..20
    spa = round(100 * rng.random())                                      # 0..100
    return {"VIT": 100, "STR": str_, "DIF": dif, "MOV": mov, "SPA": spa,
            "TABI": str_ + dif + mov + spa}


def tabi(stats: dict[str, int]) -> int:
    return stats["STR"] + stats["DIF"] + stats["MOV"] + stats["SPA"]


# ---------------------------------------------------------------------------
# §4.5 Stipendio combattente
# ---------------------------------------------------------------------------
# scaglioni esperienza per numero di missioni completate (§4.5)
_EXP_TIERS = [(89, 8), (55, 7), (34, 6), (21, 5), (13, 4), (8, 3), (5, 2), (2, 1)]


def exp_multiplier(missioni_completate: int) -> int:
    for soglia, mult in _EXP_TIERS:
        if missioni_completate >= soglia:
            return mult
    return 1


def stipendio_combattente(tabi_value: int, missioni_completate: int) -> float:
    """sqrt(TABI) / 5 * moltiplicatore_esperienza."""
    return math.sqrt(tabi_value) / 5.0 * exp_multiplier(missioni_completate)


# ---------------------------------------------------------------------------
# §5.2 Cura ospedale
# ---------------------------------------------------------------------------
def cura_giornaliera(vit_attuale: int, rng: Rng) -> int:
    heal = 20 + rng.randint(-5, 5)
    return min(100, vit_attuale + heal)


# ---------------------------------------------------------------------------
# §9.4 Modello del nemico — E(t) ibrido a fasi
# ---------------------------------------------------------------------------
def enemy_index(t: int) -> float:
    """E(t): Fase A lineare 0-60, Fase B composto giornaliero. Continua in t=60."""
    if t <= B.PHASE_A_END:
        return B.E_BASE + B.PHASE_A_SLOPE * t
    e60 = B.E_BASE + B.PHASE_A_SLOPE * B.PHASE_A_END  # 340
    return e60 * (B.PHASE_B_DAILY ** (t - B.PHASE_A_END))


def enemy_power(mission_type: MissionType, t: int, n_combattenti: int = 1) -> float:
    """Potenza del nemico Pn per piano di missione (§9.4)."""
    e = enemy_index(t)
    if mission_type == MissionType.TERRESTRE:
        return n_combattenti * e * B.K_SBARCO
    if mission_type == MissionType.INTERCETTAZIONE_TERRESTRE:
        return e * B.K_INT
    if mission_type == MissionType.INTERCETTAZIONE_LUNARE:
        return e * B.K_INT * B.K_LUNA
    if mission_type == MissionType.LUNARE:
        return n_combattenti * e * B.K_SBARCO * B.K_LUNA
    # UG / Evacuazione: gestite altrove
    return e


# ---------------------------------------------------------------------------
# §9.5 Risoluzione del combattimento — Potenza del giocatore (Pg)
# ---------------------------------------------------------------------------
def pg_intercettazione(attacco_vettore: int, somma_missili: int,
                       str_pct: float, velocita: float) -> float:
    """Piano A: (Att + missili) * (1 + STR%|STRS%) * (1 + 0.1*Velocita)."""
    return (attacco_vettore + somma_missili) * (1 + str_pct / 100.0) * (1 + 0.1 * velocita)


def pg_sbarco(tabi_efficace_per_combattente: list[int]) -> int:
    """Piano B: somma dei TABI efficaci dei combattenti schierati."""
    return sum(tabi_efficace_per_combattente)


@dataclass
class CombatResult:
    success: bool
    pg: float
    pn: float
    pg_eff: float
    pn_eff: float
    overwhelming: bool      # vittoria schiacciante (Pg' >= 2*Pn')
    danno_totale: float     # danno da ripartire sui combattenti (sbarco)


def resolve_combat(pg: float, pn: float, rng: Rng) -> CombatResult:
    """§9.5-9.6: fattore casuale +/-25% indipendente; esito e danno."""
    pg_eff = pg * rng.uniform(B.RANDOM_MIN, B.RANDOM_MAX)
    pn_eff = pn * rng.uniform(B.RANDOM_MIN, B.RANDOM_MAX)
    success = pg_eff >= pn_eff
    overwhelming = pg_eff >= 2 * pn_eff
    if success and not overwhelming:
        danno = pn_eff * 0.5             # vittoria di misura
    elif success and overwhelming:
        danno = 0.0                      # quasi nulle
    else:
        danno = pn_eff                   # sconfitta: danno massimo
    return CombatResult(success, pg, pn, pg_eff, pn_eff, overwhelming, danno)


def ripartisci_danno(danno_totale: float, dif_per_combattente: list[int]) -> list[float]:
    """§9.6: danno ripartito in proporzione INVERSA alla DIF (i piu corazzati incassano meno)."""
    pesi = [1.0 / max(1, d) for d in dif_per_combattente]
    tot = sum(pesi) or 1.0
    return [danno_totale * (p / tot) for p in pesi]


# ---------------------------------------------------------------------------
# §9.7 Ricompense
# ---------------------------------------------------------------------------
_TYPE_MULT = {
    MissionType.TERRESTRE: B.REWARD_MULT_TERRESTRE,
    MissionType.INTERCETTAZIONE_TERRESTRE: B.REWARD_MULT_INTERCETTAZIONE,
    MissionType.INTERCETTAZIONE_LUNARE: B.REWARD_MULT_LUNARE,
    MissionType.LUNARE: B.REWARD_MULT_LUNARE,
}
_ALARM_MULT = {
    AlarmLevel.VERDE: B.ALARM_MULT_VERDE,
    AlarmLevel.GIALLO: B.ALARM_MULT_GIALLO,
    AlarmLevel.ROSSO: B.ALARM_MULT_ROSSO,
}


def reward(pn: float, mission_type: MissionType, alarm: AlarmLevel) -> float:
    """Ricompensa = Pn * moltiplicatore_tipo * moltiplicatore_allarme (§9.7)."""
    return pn * _TYPE_MULT.get(mission_type, 1.0) * _ALARM_MULT.get(alarm, 1.0)


# ---------------------------------------------------------------------------
# §9.1 Assegnazione missioni
# ---------------------------------------------------------------------------
def missioni_disponibili(giocatori_attivi: int) -> int:
    return giocatori_attivi * B.MISSIONS_PER_PLAYER


def missioni_giocatore(missioni_disp: int, espo_giocatore: float, espo_totale: float) -> int:
    """MissioniGiocatore = 1 + int(disp * ESPO_g / ESPO_tot), cap 11 (§9.1)."""
    if espo_totale <= 0:
        quota = 0
    else:
        quota = int(missioni_disp * espo_giocatore / espo_totale)
    return min(B.MISSION_CAP_PER_PLAYER, 1 + quota)


# ---------------------------------------------------------------------------
# §8 Tempo di volo terrestre
# ---------------------------------------------------------------------------
def tempo_volo_terrestre(distanza: float, velocita: float) -> float:
    """t_andata = distanza(base, bersaglio) / velocita (§8)."""
    if velocita <= 0:
        raise ValueError("velocita deve essere > 0")
    return distanza / velocita


# ---------------------------------------------------------------------------
# §10 Co-finanziamento UG
# ---------------------------------------------------------------------------
def cofinanziamento_ug(missioni_ultime_48h: int) -> int:
    return B.UG_COFINANCE_PER_MISSION * missioni_ultime_48h
