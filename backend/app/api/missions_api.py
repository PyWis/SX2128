"""API Missioni — GDD §9, §9.10."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.gamedata.enums import MissionStatus, MissionType
from app.gamedata.vehicles import get_vehicle as get_bp
from app.models.core import Agency, Fighter, Mission, Pilot, User, Vehicle
from app.services.launch_service import LaunchError, launch_mission

router = APIRouter(prefix="/api/agency", tags=["missions"])


class ChainLeg(BaseModel):
    mission_id: int
    fighter_ids: list[int] = []


class LaunchRequest(BaseModel):
    vehicle_id: int
    fighter_ids: list[int] = []        # per la prima missione (sbarco)
    chain_legs: list[ChainLeg] = []    # tappe aggiuntive (§9.11)


# --- helpers ---

def _get_agency(db: Session, user: User, server_id: int) -> Agency:
    a = db.query(Agency).filter(Agency.user_id == user.id,
                                Agency.server_id == server_id).first()
    if not a:
        raise HTTPException(404, "agenzia non trovata")
    return a


def _server_day(db: Session, server_id: int) -> int:
    from app.models.core import Server
    s = db.get(Server, server_id)
    return s.current_day if s else 0


def _mission_out(m: Mission) -> dict:
    return {
        "id": m.id,
        "mission_type": m.mission_type,
        "alarm": m.alarm,
        "status": m.status,
        "target_lat": m.target_lat,
        "target_lon": m.target_lon,
        "pn": round(m.pn, 1),
        "reward_estimate": round(m.reward_estimate, 1),
        "assigned_day": m.assigned_day,
        "deadline_day": m.deadline_day,
        "vehicle_id": m.vehicle_id,
        "fighters": m.fighters_json or [],
        "sortie_return_day": m.sortie_return_day,
        "chain_leg": m.chain_leg,
        "civili_da_salvare": m.civili_da_salvare,
        "resolution": m.resolution_json,
    }


# --- endpoints ---

@router.get("/{server_id}/missions")
def list_missions(server_id: int, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> list:
    agency = _get_agency(db, user, server_id)
    missions = db.query(Mission).filter(
        Mission.agency_id == agency.id,
        Mission.status.in_([
            MissionStatus.ASSIGNED.value,
            MissionStatus.IN_PROGRESS.value,
            MissionStatus.COMPLETED.value,
            MissionStatus.FAILED.value,
        ]),
    ).order_by(Mission.assigned_day.desc()).limit(50).all()
    return [_mission_out(m) for m in missions]


@router.get("/{server_id}/missions/active")
def list_active_missions(server_id: int, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)) -> list:
    agency = _get_agency(db, user, server_id)
    missions = db.query(Mission).filter(
        Mission.agency_id == agency.id,
        Mission.status == MissionStatus.ASSIGNED.value,
    ).all()
    return [_mission_out(m) for m in missions]


@router.get("/{server_id}/missions/inflight")
def list_inflight(server_id: int, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> list:
    agency = _get_agency(db, user, server_id)
    missions = db.query(Mission).filter(
        Mission.agency_id == agency.id,
        Mission.status == MissionStatus.IN_PROGRESS.value,
    ).all()
    return [_mission_out(m) for m in missions]


@router.post("/{server_id}/missions/{mission_id}/launch")
def api_launch_mission(
    server_id: int, mission_id: int, payload: LaunchRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> dict:
    agency = _get_agency(db, user, server_id)
    day = _server_day(db, server_id)
    chain = [{"mission_id": l.mission_id, "fighter_ids": l.fighter_ids}
             for l in payload.chain_legs]
    try:
        result = launch_mission(
            db, agency, mission_id,
            payload.vehicle_id, payload.fighter_ids, day,
            chain_legs=chain,
        )
    except LaunchError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return result


@router.get("/{server_id}/missions/{mission_id}/simulate")
def simulate_mission(
    server_id: int, mission_id: int, vehicle_id: int,
    fighter_ids: str = "",
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> dict:
    """§9.10 — Simulatore: restituisce Pg, banda ±25%, probabilità di successo (stima)."""
    from app.services.combat import _calc_pg, _tabi_efficace
    from app.services import formulas as F
    from app.gamedata import balance as B

    agency = _get_agency(db, user, server_id)
    mission = db.query(Mission).filter(
        Mission.id == mission_id, Mission.agency_id == agency.id
    ).first()
    if not mission:
        raise HTTPException(404, "missione non trovata")

    vehicle = next((v for v in agency.vehicles if v.id == vehicle_id), None)
    if not vehicle:
        raise HTTPException(404, "vettore non trovato")

    pilot = next((p for p in agency.pilots if p.id == vehicle.pilot_id), None)
    fids = [int(x) for x in fighter_ids.split(",") if x.strip()]
    fighters = [f for f in agency.fighters if f.id in fids]

    pg = _calc_pg(mission, vehicle, pilot, fighters)
    pn = mission.pn

    pg_min = pg * B.RANDOM_MIN
    pg_max = pg * B.RANDOM_MAX
    pn_min = pn * B.RANDOM_MIN
    pn_max = pn * B.RANDOM_MAX

    # stima probabilità: frazione in cui pg_eff >= pn_eff
    # pg_eff ~ U[pg*0.75, pg*1.25], pn_eff ~ U[pn*0.75, pn*1.25]
    # P(pg_eff >= pn_eff) ≈ P(X - Y >= 0) con triangolare
    # Approssimazione semplice: confronto le bande
    if pg_min >= pn_max:
        prob = 1.0
    elif pg_max <= pn_min:
        prob = 0.0
    else:
        # overlap lineare approssimato
        overlap = min(pg_max, pn_max) - max(pg_min, pn_min)
        spread = (pg_max - pg_min) + (pn_max - pn_min)
        prob = round(max(0.0, min(1.0, 0.5 + (pg - pn) / (spread or 1))), 2)

    return {
        "pg": round(pg, 1),
        "pg_min": round(pg_min, 1),
        "pg_max": round(pg_max, 1),
        "pn": round(pn, 1),
        "pn_min": round(pn_min, 1),
        "pn_max": round(pn_max, 1),
        "prob_successo": prob,
    }
