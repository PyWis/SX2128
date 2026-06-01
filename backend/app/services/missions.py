"""Generazione e assegnazione missioni — GDD §9.1-9.4, §9.7."""
from __future__ import annotations

import random

from sqlalchemy.orm import Session

from app.gamedata import balance as B
from app.gamedata.enums import AlarmLevel, MissionStatus, MissionType
from app.models.core import Agency, Mission, Server
from app.services import formulas as F

# §9.3 giorni di sblocco (offset da day 0 = 1 luglio 2128)
UNLOCK_DAY = {
    MissionType.TERRESTRE: 0,                  # 1 luglio
    MissionType.INTERCETTAZIONE_TERRESTRE: 45, # 15 agosto
    MissionType.EVACUAZIONE: 50,               # inizio agosto
    MissionType.INTERCETTAZIONE_LUNARE: 92,    # 1 ottobre
    MissionType.LUNARE: 123,                   # 1 novembre
    MissionType.UG: 30,                        # missioni UG dal giorno 30
}

# §9.8 — una missione UG ogni N giorni
UG_MISSION_INTERVAL = 5
# moltiplicatore Pn per missioni UG
UG_PN_MULT = 3.0

# dimensione squadra di riferimento per stimare Pn degli sbarchi
_REF_SQUAD = 8


def _unlocked_types(day: int) -> list[MissionType]:
    return [t for t, d in UNLOCK_DAY.items() if day >= d]


def _make_mission(db: Session, server: Server, agency: Agency | None,
                  mtype: MissionType, day: int, rng: random.Random) -> Mission:
    if mtype == MissionType.EVACUAZIONE:
        from app.services.formulas import enemy_index
        et = enemy_index(day)
        civili = int(et * B.K_CIVILI_EVACUAZIONE)
        tariff = B.EVACUAZIONE_TARIFF
        reward = min(B.REF_CAPACITA_H_EVAC, civili) * tariff
        m = Mission(
            server_id=server.id,
            agency_id=agency.id if agency else None,
            mission_type=mtype.value,
            alarm=AlarmLevel.VERDE.value,
            status=MissionStatus.ASSIGNED.value,
            target_lat=rng.uniform(-60, 70),
            target_lon=rng.uniform(-180, 180),
            pn=0.0,                             # no combat
            reward_estimate=round(reward, 1),
            assigned_day=day,
            deadline_day=day + B.ALARM_VERDE_DAYS,
            visible_at_hour=rng.randint(0, 23),
            civili_da_salvare=civili,
        )
        db.add(m)
        return m

    n = _REF_SQUAD if mtype in (MissionType.TERRESTRE, MissionType.LUNARE) else 1
    pn = F.enemy_power(mtype, day, n_combattenti=n)
    reward = F.reward(pn, mtype, AlarmLevel.VERDE)
    m = Mission(
        server_id=server.id,
        agency_id=agency.id if agency else None,
        mission_type=mtype.value,
        alarm=AlarmLevel.VERDE.value,
        status=MissionStatus.ASSIGNED.value,
        target_lat=rng.uniform(-60, 70),
        target_lon=rng.uniform(-180, 180),
        pn=pn,
        reward_estimate=round(reward, 1),
        assigned_day=day,
        deadline_day=day + B.ALARM_VERDE_DAYS,
        visible_at_hour=rng.randint(0, 23),
    )
    db.add(m)
    return m


def _make_ug_mission(db: Session, server: Server, day: int, rng: random.Random) -> Mission:
    """§9.8 — missione UG ad alto rischio/ricompensa, visibile a tutti."""
    n = _REF_SQUAD
    pn = F.enemy_power(MissionType.TERRESTRE, day, n_combattenti=n) * UG_PN_MULT
    reward = F.reward(pn, MissionType.TERRESTRE, AlarmLevel.VERDE) * 2.0  # ricompensa doppia
    m = Mission(
        server_id=server.id,
        agency_id=None,
        mission_type=MissionType.UG.value,
        alarm=AlarmLevel.VERDE.value,
        status=MissionStatus.AVAILABLE.value,   # subito visibile a tutti
        target_lat=rng.uniform(-60, 70),
        target_lon=rng.uniform(-180, 180),
        pn=pn,
        reward_estimate=round(reward, 1),
        assigned_day=day,
        deadline_day=day + B.ALARM_VERDE_DAYS,
        visible_at_hour=0,
    )
    db.add(m)
    return m


def assign_daily_missions(db: Session, server: Server, day: int,
                          rng: random.Random | None = None) -> int:
    """§9.1: distribuisce le missioni del giorno alle agenzie attive in base all'ESPO."""
    rng = rng or random.Random()
    active = [a for a in db.query(Agency).filter(
        Agency.server_id == server.id, Agency.active == True,  # noqa: E712
        Agency.cut_by_ug == False).all()]  # noqa: E712
    if not active:
        return 0

    # §9.3 filtra UG dai tipi normali (generata separatamente)
    regular_types = [t for t in _unlocked_types(day) if t != MissionType.UG]
    if not regular_types:
        return 0

    disponibili = F.missioni_disponibili(len(active))
    espo_tot = sum(a.espo_today for a in active)

    created = 0
    for agency in active:
        n = F.missioni_giocatore(disponibili, agency.espo_today, espo_tot)
        for _ in range(n):
            mtype = rng.choice(regular_types)
            _make_mission(db, server, agency, mtype, day, rng)
            created += 1

    # §9.8 missione UG ogni UG_MISSION_INTERVAL giorni a partire dal day 30
    if day >= UNLOCK_DAY[MissionType.UG] and day % UG_MISSION_INTERVAL == 0:
        _make_ug_mission(db, server, day, rng)
        created += 1

    db.flush()
    return created
