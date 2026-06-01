"""Motore di simulazione Monte Carlo — GDD §9.4, §14 (F7).

Valida i coefficienti di combattimento su N prove per scenario.
Ogni prova applica il fattore casuale ±25% su Pg e Pn indipendentemente.
"""
from __future__ import annotations

import random
import statistics

from app.gamedata import balance as B
from app.services import formulas as F
from app.gamedata.enums import MissionType, AlarmLevel


def combat_simulation(
    pg: float,
    pn: float,
    n: int = 10_000,
    rng_seed: int | None = 42,
) -> dict:
    """Simula N combattimenti con Pg fisso vs Pn fisso (fattore casuale per entrambi).

    Ritorna: win_rate, overwhelming_rate, distribuzione danno, breakeven Pg.
    """
    rng = random.Random(rng_seed)
    wins = 0
    overwhelming_wins = 0
    damages: list[float] = []

    for _ in range(n):
        result = F.resolve_combat(pg, pn, rng)
        if result.success:
            wins += 1
            if result.overwhelming:
                overwhelming_wins += 1
        damages.append(result.danno_totale)

    win_rate = wins / n
    return {
        "pg": round(pg, 2),
        "pn": round(pn, 2),
        "pg_pn_ratio": round(pg / pn, 3) if pn else None,
        "n": n,
        "win_rate": round(win_rate, 4),
        "overwhelming_rate": round(overwhelming_wins / n, 4),
        "avg_damage": round(statistics.mean(damages), 2),
        "median_damage": round(statistics.median(damages), 2),
        "max_damage": round(max(damages), 2),
    }


def breakeven_pg(pn: float, target_win_rate: float = 0.5,
                 n: int = 5_000, tol: float = 0.01) -> float:
    """Trova il Pg che dà circa target_win_rate con ricerca binaria."""
    lo, hi = pn * 0.1, pn * 3.0
    for _ in range(20):
        mid = (lo + hi) / 2
        wr = combat_simulation(mid, pn, n=n)["win_rate"]
        if abs(wr - target_win_rate) < tol:
            break
        if wr < target_win_rate:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 2)


def income_band_report(days: list[int] | None = None) -> list[dict]:
    """Calcola la banda di reddito R/g per giorno di gioco.

    Considera: cultura europea (base), 0 missioni/48h (min) e 5 missioni/48h (max).
    """
    from app.gamedata.cultures import get_culture
    from app.services.formulas import contributo_fazione, cofinanziamento_ug

    if days is None:
        days = [0, 15, 30, 60, 90, 120, 150, 200]

    cultures_sample = ["europea", "latinoamericana", "cyber"]   # min/mid/max ESPO multiplier
    rows = []
    for t in days:
        et = F.enemy_index(t)
        for cid in cultures_sample:
            c = get_culture(cid)
            loyalty = t  # approssimazione: fedeltà = giorni di gioco
            contrib = contributo_fazione(c.base_r_giorno, c.fedelta_pct_giorno, loyalty)
            # §10: 100 R × missioni ultime 48h (min=0, max=5)
            cofin_min = cofinanziamento_ug(0)
            cofin_max = cofinanziamento_ug(5)
            rows.append({
                "t": t, "E": round(et, 1), "cultura": cid,
                "contributo": round(contrib, 1),
                "reddito_min_R_g": round(contrib + cofin_min, 1),
                "reddito_max_R_g": round(contrib + cofin_max, 1),
            })
    return rows


def k_luna_analysis(n: int = 10_000) -> dict:
    """Compara win rate Intercettazione Terra vs Luna allo stesso giorno (§14, questione aperta)."""
    t = 60  # giorno 60: inizio Fase B
    pn_terra = F.enemy_power(MissionType.INTERCETTAZIONE_TERRESTRE, t)
    pn_luna = F.enemy_power(MissionType.INTERCETTAZIONE_LUNARE, t)

    # Pg tipico per un caccia con 2 missili bronze (approssimazione)
    pg_typical = 300.0

    sim_terra = combat_simulation(pg_typical, pn_terra, n=n)
    sim_luna = combat_simulation(pg_typical, pn_luna, n=n)

    return {
        "t": t,
        "E_t": round(F.enemy_index(t), 1),
        "k_luna": B.K_LUNA,
        "terra": {"pn": pn_terra, **sim_terra},
        "luna": {"pn": pn_luna, **sim_luna},
        "win_ratio_luna_vs_terra": round(sim_luna["win_rate"] / sim_terra["win_rate"], 3)
        if sim_terra["win_rate"] > 0 else None,
        "recommendation": (
            "k_luna=1.5 bilancia l'intercettazione lunare come difficile ma accessibile"
            if B.K_LUNA == 1.5 else
            "verifica k_luna nel pass Monte Carlo"
        ),
    }
