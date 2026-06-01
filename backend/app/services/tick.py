"""Motore del tick giornaliero — GDD §0.1.

Sequenza (§0.1):
  1. accredita contributo fazione + co-finanziamento UG
  2. addebita manutenzione, rate prestiti, stipendi, addestramento
  3. aggiorna ESPO, classifica, bilancio
  4. assegna nuove missioni; rientro vettori secondo i timer
Idempotente per (server, giorno): rieseguire lo stesso giorno non duplica gli effetti.
"""
from __future__ import annotations

import random
from datetime import timedelta

from sqlalchemy.orm import Session

from app.gamedata import balance as B
from app.gamedata.buildings import (
    FIGHTER_LIMITS, FIGHTER_VIT_MAX, FIGHTER_VIT_REGEN,
    HOSPITAL_HEAL_BASE, VIT_MAX_HEAL,
)
from app.gamedata.enums import MissionStatus
from app.models.core import Agency, Mission, Server
from app.services import economy
from app.services.missions import assign_daily_missions


def _is_active(agency: Agency, now) -> bool:
    """§9.1: attivo se ultimo login <= 48h."""
    if agency.last_login is None:
        return False
    delta = now - agency.last_login.replace(tzinfo=now.tzinfo)
    return delta <= timedelta(hours=B.INACTIVE_AFTER_HOURS)


def _process_training(agency: Agency, day: int, rng: random.Random) -> None:
    """Completa addestramenti piloti e combattenti al giorno corrente."""
    # §4.2/§4.3 — piloti: training_info = "lic:<type>:<tier>" o "stat:<stat>"
    for p in agency.pilots:
        if p.status == "training" and p.training_until_day is not None:
            if day >= p.training_until_day:
                info = p.training_info or ""
                if info.startswith("stat:"):
                    # addestramento stat pilota: +1%
                    stat = info[5:]  # "espo", "str" o "strs"
                    attr = f"{stat}_pct"
                    current = getattr(p, attr, 0.0)
                    setattr(p, attr, round(min(25.0, current + 1.0), 1))
                elif info.startswith("lic:"):
                    # addestramento licenza: assegna la licenza
                    _, lic_type, lic_tier = info.split(":")
                    p.licenses = {**p.licenses, lic_type: lic_tier}
                p.status = "barracks"
                p.training_until_day = None
                p.training_info = None

    # §4.4 — combattenti
    stat_map = {"STR": "strg", "DIF": "dif", "MOV": "mov", "SPA": "spa"}
    for f in agency.fighters:
        if f.training_until_day is not None and day >= f.training_until_day:
            if f.training_stat:
                attr = stat_map.get(f.training_stat)
                cap = FIGHTER_LIMITS.get(f.training_stat, 200)
                if attr:
                    setattr(f, attr, min(cap, getattr(f, attr) + 1))
            f.training_until_day = None
            f.training_stat = None
            if f.status == "training":
                f.status = "barracks"


def _process_hospital(agency: Agency, rng: random.Random) -> None:
    """§5.2 — guarigione giornaliera in ospedale: VIT += 20 ± 5, max 100."""
    for f in agency.fighters:
        if f.status != "hospital":
            continue
        heal = HOSPITAL_HEAL_BASE + rng.randint(-5, 5)
        f.vit = min(VIT_MAX_HEAL, f.vit + heal)
        if f.vit >= VIT_MAX_HEAL:
            f.status = "barracks"  # dimissione automatica a piena salute


def _resolve_sorties(db: Session, agency: Agency, day: int, rng: random.Random) -> list[dict]:
    """§9 — risolve le sortie il cui return_day <= giorno corrente."""
    from app.services.combat import resolve_mission

    logs = []
    in_progress = db.query(Mission).filter(
        Mission.agency_id == agency.id,
        Mission.status == MissionStatus.IN_PROGRESS.value,
        Mission.sortie_return_day <= day,
    ).all()

    for mission in in_progress:
        # recupera vettore e unità
        vehicle = next((v for v in agency.vehicles if v.id == mission.vehicle_id), None)
        if not vehicle:
            mission.status = MissionStatus.FAILED.value
            continue

        pilot = next((p for p in agency.pilots if p.id == vehicle.pilot_id), None)
        fighter_ids = mission.fighters_json or []
        fighters = [f for f in agency.fighters if f.id in fighter_ids]

        log = resolve_mission(mission, vehicle, pilot, fighters, agency, rng)
        mission.status = (
            MissionStatus.COMPLETED.value if log["success"]
            else MissionStatus.FAILED.value
        )
        mission.resolution_json = log
        logs.append(log)
    return logs


def run_tick(db: Session, server: Server, rng: random.Random | None = None) -> dict:
    """Avanza il server di un giorno di gioco e ritorna un riepilogo."""
    from app.models.core import utcnow
    rng = rng or random.Random()
    now = utcnow()
    server.current_day += 1
    day = server.current_day

    agencies = db.query(Agency).filter(Agency.server_id == server.id).all()
    summary = {"server_id": server.id, "day": day, "agencies": []}

    for agency in agencies:
        if agency.cut_by_ug:
            continue
        # §9.1 inattivita: oltre 48h l'agenzia e rimossa
        agency.active = _is_active(agency, now)
        if not agency.active:
            summary["agencies"].append({"id": agency.id, "status": "inattiva"})
            continue

        # fedelta lineare cresce di 1 giorno (§1)
        agency.loyalty_days += 1

        # §4.4 — +1 VIT/g gratis in caserma (max 120)
        for f in agency.fighters:
            if f.status == "barracks" and f.vit < FIGHTER_VIT_MAX:
                f.vit = min(FIGHTER_VIT_MAX, f.vit + FIGHTER_VIT_REGEN)

        # §5.2 — guarigione ospedale
        _process_hospital(agency, rng)

        # §4.2/§4.3/§4.4 — completamento addestramenti
        _process_training(agency, day, rng)

        # §9 — risoluzione sortie rientrate
        sortie_logs = _resolve_sorties(db, agency, day, rng)

        # economia del giorno (missioni completate nelle ultime 48h per co-finanziamento)
        missioni_48h = len([s for s in sortie_logs if s.get("success")])
        ledger = economy.apply_daily(db, agency, missioni_48h=missioni_48h)

        # reset flag reclutamento giornaliero
        agency.recruited_today = False

        summary["agencies"].append({
            "id": agency.id, "saldo": round(agency.balance, 2),
            "netto": round(ledger.netto, 2), "espo": round(agency.espo_today, 2),
            "in_default": agency.in_default,
            "sortie_risolte": len(sortie_logs),
        })

    # assegnazione missioni del nuovo giorno (§9.1)
    assigned = assign_daily_missions(db, server, day)
    summary["missioni_assegnate"] = assigned

    db.flush()
    return summary
