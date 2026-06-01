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
from app.gamedata.enums import AlarmLevel, MissionStatus
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
    for p in agency.pilots:
        if p.status == "training" and p.training_until_day is not None:
            if day >= p.training_until_day:
                info = p.training_info or ""
                if info.startswith("stat:"):
                    stat = info[5:]
                    attr = f"{stat}_pct"
                    current = getattr(p, attr, 0.0)
                    setattr(p, attr, round(min(25.0, current + 1.0), 1))
                elif info.startswith("lic:"):
                    _, lic_type, lic_tier = info.split(":")
                    p.licenses = {**p.licenses, lic_type: lic_tier}
                p.status = "barracks"
                p.training_until_day = None
                p.training_info = None

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
    for f in agency.fighters:
        if f.status != "hospital":
            continue
        heal = HOSPITAL_HEAL_BASE + rng.randint(-5, 5)
        f.vit = min(VIT_MAX_HEAL, f.vit + heal)
        if f.vit >= VIT_MAX_HEAL:
            f.status = "barracks"


def _resolve_sorties(db: Session, agency: Agency, day: int, rng: random.Random) -> list[dict]:
    """§9 / §9.11 — risolve sortie il cui return_day <= giorno corrente, gestisce catene."""
    from app.services.combat import resolve_mission

    logs = []
    in_progress = db.query(Mission).filter(
        Mission.agency_id == agency.id,
        Mission.status == MissionStatus.IN_PROGRESS.value,
        Mission.sortie_return_day <= day,
    ).all()

    # raggruppa per vehicle_id (ogni vettore ha al più una catena attiva)
    by_vehicle: dict[int, list[Mission]] = {}
    for m in in_progress:
        if m.vehicle_id not in by_vehicle:
            by_vehicle[m.vehicle_id] = []
        by_vehicle[m.vehicle_id].append(m)

    for vehicle_id, missions in by_vehicle.items():
        missions.sort(key=lambda m: m.chain_leg)
        vehicle = next((v for v in agency.vehicles if v.id == vehicle_id), None)
        if not vehicle:
            for m in missions:
                m.status = MissionStatus.FAILED.value
            continue

        pilot = next((p for p in agency.pilots if p.id == vehicle.pilot_id), None)
        chain_aborted = False

        for i, mission in enumerate(missions):
            if chain_aborted:
                mission.status = MissionStatus.FAILED.value
                continue

            is_final = (i == len(missions) - 1)
            fighter_ids = mission.fighters_json or []
            fighters = [f for f in agency.fighters if f.id in fighter_ids]

            log = resolve_mission(
                mission, vehicle, pilot, fighters, agency, rng,
                is_final_leg=is_final,
            )
            mission.status = (MissionStatus.COMPLETED.value if log["success"]
                              else MissionStatus.FAILED.value)
            mission.resolution_json = log
            logs.append(log)

            # §12 split ricompensa missione trasferita (25% solver / 75% transferente)
            if log["success"] and mission.transferred_from_agency_id:
                full = log.get("ricompensa", 0.0)
                solver_share = round(full * B.TRANSFER_SOLVER_SHARE, 2)
                transferer_share = round(full - solver_share, 2)
                agency.balance -= (full - solver_share)   # corregge a 25%
                transferer = db.get(Agency, mission.transferred_from_agency_id)
                if transferer:
                    transferer.balance += transferer_share
                log["solver_share"] = solver_share
                log["transferer_share"] = transferer_share

            if log.get("vehicle_lost"):
                chain_aborted = True

        # se la catena è completata e il vettore non è eliminato, ritorna in hangar
        if not chain_aborted and vehicle.status == "in_flight":
            vehicle.status = "barracks"
            vehicle.return_day = None
            if pilot and pilot.status == "in_flight":
                pilot.status = "barracks"

    return logs


def _escalate_alarms(db: Session, server_id: int, day: int) -> int:
    """§9.2 — Verde→Giallo→Rosso→FAILED per missioni non eseguite."""
    resolved = 0

    # Verde → Giallo quando la scadenza Verde è passata
    verde = db.query(Mission).filter(
        Mission.server_id == server_id,
        Mission.status == MissionStatus.ASSIGNED.value,
        Mission.alarm == AlarmLevel.VERDE.value,
        Mission.deadline_day <= day,
    ).all()
    for m in verde:
        m.alarm = AlarmLevel.GIALLO.value
        m.deadline_day = m.assigned_day + B.ALARM_ROSSO_DAY   # scadenza al giorno 12

    # Giallo → Rosso
    giallo = db.query(Mission).filter(
        Mission.server_id == server_id,
        Mission.status == MissionStatus.ASSIGNED.value,
        Mission.alarm == AlarmLevel.GIALLO.value,
        Mission.deadline_day <= day,
    ).all()
    for m in giallo:
        m.alarm = AlarmLevel.ROSSO.value
        m.deadline_day = m.assigned_day + B.ALARM_ROSSO_DAY + 2  # UG risolve dopo 48h

    # Rosso → UG risolve (FAILED)
    rosso = db.query(Mission).filter(
        Mission.server_id == server_id,
        Mission.status == MissionStatus.ASSIGNED.value,
        Mission.alarm == AlarmLevel.ROSSO.value,
        Mission.deadline_day <= day,
    ).all()
    for m in rosso:
        m.status = MissionStatus.FAILED.value
        resolved += 1

    return resolved


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
        agency.active = _is_active(agency, now)
        if not agency.active:
            summary["agencies"].append({"id": agency.id, "status": "inattiva"})
            continue

        agency.loyalty_days += 1

        # §4.4 — +1 VIT/g in caserma
        for f in agency.fighters:
            if f.status == "barracks" and f.vit < FIGHTER_VIT_MAX:
                f.vit = min(FIGHTER_VIT_MAX, f.vit + FIGHTER_VIT_REGEN)

        # §5.2 — guarigione ospedale
        _process_hospital(agency, rng)

        # §4.2/§4.3/§4.4 — completamento addestramenti
        _process_training(agency, day, rng)

        # §9 / §9.11 — risoluzione sortie rientrate
        sortie_logs = _resolve_sorties(db, agency, day, rng)

        # economia del giorno
        missioni_48h = len([s for s in sortie_logs if s.get("success")])
        ledger = economy.apply_daily(db, agency, missioni_48h=missioni_48h)

        agency.recruited_today = False

        summary["agencies"].append({
            "id": agency.id, "saldo": round(agency.balance, 2),
            "netto": round(ledger.netto, 2), "espo": round(agency.espo_today, 2),
            "in_default": agency.in_default,
            "sortie_risolte": len(sortie_logs),
        })

    # §9.2 — escalation allarmi per tutto il server
    ug_resolved = _escalate_alarms(db, server.id, day)

    # §9.1 — assegnazione missioni del nuovo giorno
    assigned = assign_daily_missions(db, server, day)
    summary["missioni_assegnate"] = assigned
    summary["ug_resolved"] = ug_resolved

    # §11 — Taglio UG al termine di ogni ciclo di 40 giorni
    taglio_result = None
    if day > 0 and day % B.CYCLE_DAYS == 0:
        from app.services.taglio_service import run_ciclo_taglio
        taglio_result = run_ciclo_taglio(db, server, day, rng)
        summary["taglio"] = taglio_result

        # Notifica Delpy
        from app.services.chat_service import post_delpy
        n_tagliati = len(taglio_result.get("tagliati", []))
        post_delpy(db, server.id,
                   f"[Sistema] Ciclo {server.cycle - 1} concluso. "
                   f"Taglio UG: {n_tagliati} agenzie eliminate. "
                   f"Superstiti: {taglio_result.get('survivors', '?')}.")

    db.flush()
    return summary
