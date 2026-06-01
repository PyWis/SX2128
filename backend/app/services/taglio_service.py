"""Ciclo 40 giorni, Taglio UG, Trasporto Coloni, endgame — GDD §11."""
from __future__ import annotations

import math

from sqlalchemy.orm import Session

from app.gamedata import balance as B
from app.models.core import Agency, Alliance, Server


def run_ciclo_taglio(db: Session, server: Server, day: int, rng) -> dict:
    """Esegue il Taglio UG alla fine di un ciclo di 40 giorni.

    Sequenza (§11):
    1. Trasporto Coloni: top 50% agenzie attive ricevono +25 missioni equivalenti
    2. Taglio UG: il 25% peggiore per missioni completate viene eliminato
    3. Verifica condizione endgame
    """
    agencies = db.query(Agency).filter(
        Agency.server_id == server.id,
        Agency.cut_by_ug == False,   # noqa: E712
    ).all()

    if not agencies:
        return {"tagliati": [], "trasporto_coloni_vincitori": [], "endgame": server.finished}

    sorted_asc = sorted(agencies, key=lambda a: (a.missions_completed, a.espo_total))

    # §11 Trasporto Coloni — top 50% riceve bonus equivalente a 25 missioni
    top_half_count = math.ceil(len(sorted_asc) / 2)
    top_half = sorted_asc[-top_half_count:]
    for a in top_half:
        a.missions_completed += B.TRASPORTO_COLONI_VALUE

    # §11 Taglio UG 25% peggiore (dopo il bonus Trasporto Coloni)
    re_sorted = sorted(agencies, key=lambda a: (a.missions_completed, a.espo_total))
    cut_count = max(1, math.floor(len(agencies) * B.UG_CUT_FRACTION))
    bottom = re_sorted[:cut_count]
    tagliati_ids = []
    for a in bottom:
        a.cut_by_ug = True
        tagliati_ids.append(a.id)

    server.cycle += 1

    survivors = [a for a in agencies if not a.cut_by_ug]
    endgame = _check_endgame(db, server, survivors)

    return {
        "tagliati": tagliati_ids,
        "trasporto_coloni_vincitori": [a.id for a in top_half],
        "cycle": server.cycle,
        "survivors": len(survivors),
        "endgame": endgame,
    }


def _check_endgame(db: Session, server: Server, survivors: list[Agency]) -> bool:
    """§11.1 — verifica e avanza la condizione di endgame."""
    if server.finished:
        return True

    n = len(survivors)

    # Endgame: solo 3 alleanze superstiti (max ~84 agenzie)
    if n <= B.ENDGAME_ALLIANCES * B.ALLIANCE_MAX_MEMBERS:
        alliances = db.query(Alliance).filter(
            Alliance.server_id == server.id,
        ).all()
        # Conta alleanze con almeno un membro ancora attivo
        active_alliances = [
            al for al in alliances
            if any(a.alliance_id == al.id and not a.cut_by_ug for a in survivors)
        ]
        if len(active_alliances) <= B.ENDGAME_ALLIANCES:
            server.finished = True
            return True

    return False
