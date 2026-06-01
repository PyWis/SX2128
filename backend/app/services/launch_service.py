"""Lancio di una missione — GDD §9.10, §8, §9.11."""
from __future__ import annotations

import math

from sqlalchemy.orm import Session

from app.gamedata import balance as B
from app.gamedata.enums import MissionStatus, MissionType, VehicleClass
from app.gamedata.vehicles import get_vehicle
from app.models.core import Agency, Fighter, Mission, Pilot, Vehicle

MACH_KMH = 1235.0


class LaunchError(Exception):
    pass


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _eta_days(distanza_km: float, velocita: float) -> float:
    """ETA andata+ritorno (2×distanza) in giorni."""
    if velocita <= 0:
        return 1.0
    ore = (2 * distanza_km) / (velocita * MACH_KMH)
    return max(1.0, ore / 24.0)


def _eta_chain_days(waypoints: list[tuple[float, float]], velocita: float) -> float:
    """ETA catena: base→w1→w2→…→wN→base in giorni."""
    if velocita <= 0:
        return 1.0
    total_km = sum(
        _haversine_km(waypoints[i][0], waypoints[i][1],
                      waypoints[i + 1][0], waypoints[i + 1][1])
        for i in range(len(waypoints) - 1)
    )
    ore = total_km / (velocita * MACH_KMH)
    return max(1.0, ore / 24.0)


def _is_space_mission(mtype: MissionType) -> bool:
    return mtype in (MissionType.INTERCETTAZIONE_LUNARE,
                     MissionType.LUNARE,
                     MissionType.EVACUAZIONE)


def _get_mission(agency: Agency, mission_id: int, db: Session) -> Mission:
    # missione propria
    m = db.query(Mission).filter(
        Mission.id == mission_id, Mission.agency_id == agency.id
    ).first()
    if m:
        return m
    # §12 pool alleanza (agency_id = NULL, alliance_id corrisponde)
    if agency.alliance_id:
        m = db.query(Mission).filter(
            Mission.id == mission_id,
            Mission.agency_id.is_(None),
            Mission.alliance_id == agency.alliance_id,
        ).first()
        if m:
            m.agency_id = agency.id   # claim: assegna all'agenzia risolutrice
            return m
    # §9.8 missioni UG disponibili a tutti
    m = db.query(Mission).filter(
        Mission.id == mission_id,
        Mission.agency_id.is_(None),
        Mission.alliance_id.is_(None),
        Mission.status == "available",
    ).first()
    if m:
        m.agency_id = agency.id
        return m
    raise LaunchError("missione non trovata o non assegnata all'agenzia")


def _get_vehicle(agency: Agency, vehicle_id: int) -> Vehicle:
    for v in agency.vehicles:
        if v.id == vehicle_id:
            return v
    raise LaunchError("vettore non trovato nell'agenzia")


def _get_fighters(agency: Agency, fighter_ids: list[int]) -> list[Fighter]:
    fm = {f.id: f for f in agency.fighters}
    result = []
    for fid in fighter_ids:
        if fid not in fm:
            raise LaunchError(f"combattente {fid} non trovato nell'agenzia")
        result.append(fm[fid])
    return result


def _check_mission_state(mission: Mission) -> None:
    if mission.status not in (MissionStatus.ASSIGNED.value,):
        raise LaunchError(f"missione non disponibile per il lancio (stato: {mission.status})")


def _check_vehicle_state(vehicle: Vehicle) -> None:
    if vehicle.status == "eliminated":
        raise LaunchError("vettore eliminato")
    if vehicle.status == "in_flight":
        raise LaunchError("vettore gia in volo")


def _check_fighters_state(fighters: list[Fighter], vehicle: Vehicle) -> None:
    bp = get_vehicle(vehicle.project)
    if len(fighters) > bp.postazioni:
        raise LaunchError(
            f"troppi combattenti: {len(fighters)} > postazioni disponibili ({bp.postazioni})"
        )
    for f in fighters:
        if f.status in ("eliminated", "in_flight", "training"):
            raise LaunchError(f"combattente {f.name!r} non disponibile (stato: {f.status})")


def _require_vehicle_type(mission_type: MissionType, vehicle: Vehicle) -> None:
    """Valida compatibilità tipo vettore ↔ tipo missione (§9.3)."""
    vclass = vehicle.vclass
    if mission_type == MissionType.TERRESTRE:
        allowed = {VehicleClass.MISSION.value}
    elif mission_type == MissionType.INTERCETTAZIONE_TERRESTRE:
        allowed = {VehicleClass.FIGHTER.value}
    elif mission_type == MissionType.INTERCETTAZIONE_LUNARE:
        allowed = {VehicleClass.SPACE_FIGHTER.value}
    elif mission_type == MissionType.LUNARE:
        allowed = {VehicleClass.SPACE_MISSION.value}
    elif mission_type == MissionType.EVACUAZIONE:
        allowed = {VehicleClass.CIVILIAN.value}
    else:
        return

    if vclass not in allowed:
        raise LaunchError(
            f"vettore di classe '{vclass}' non adatto per missione {mission_type.value} "
            f"(richiesto: {allowed})"
        )


def launch_mission(
    db: Session,
    agency: Agency,
    mission_id: int,
    vehicle_id: int,
    fighter_ids: list[int],
    current_day: int,
    chain_legs: list[dict] | None = None,
) -> dict:
    """Lancia una missione (singola o catena multi-tappa §9.11).

    chain_legs = [{"mission_id": int, "fighter_ids": list[int]}, ...]
    Massimo CHAIN_MAX_LEGS - 1 tappe aggiuntive oltre alla prima.
    """
    mission = _get_mission(agency, mission_id, db)
    _check_mission_state(mission)

    vehicle = _get_vehicle(agency, vehicle_id)
    _check_vehicle_state(vehicle)

    mtype = MissionType(mission.mission_type)
    _require_vehicle_type(mtype, vehicle)

    is_intercept = mtype in (MissionType.INTERCETTAZIONE_TERRESTRE,
                             MissionType.INTERCETTAZIONE_LUNARE)
    is_evacuazione = mtype == MissionType.EVACUAZIONE

    # intercettazione: pilota obbligatorio
    pilot: Pilot | None = None
    if is_intercept:
        if not vehicle.pilot_id:
            raise LaunchError("nessun pilota assegnato al vettore (§8)")
        pilot = next((p for p in agency.pilots if p.id == vehicle.pilot_id), None)
        if not pilot or pilot.status in ("eliminated", "training"):
            raise LaunchError("pilota non disponibile")

    # sbarco: almeno 1 combattente (non per evacuazione)
    fighters: list[Fighter] = []
    if not is_intercept and not is_evacuazione:
        if not fighter_ids:
            raise LaunchError("sbarco richiede almeno 1 combattente")
        fighters = _get_fighters(agency, fighter_ids)
        _check_fighters_state(fighters, vehicle)

    # calcola tappe aggiuntive (chain)
    chain_legs = chain_legs or []
    if len(chain_legs) >= B.CHAIN_MAX_LEGS:
        raise LaunchError(f"catena troppo lunga: max {B.CHAIN_MAX_LEGS} tappe totali")

    chain_missions: list[Mission] = []
    chain_fighters_per_leg: list[list[Fighter]] = []
    for leg in chain_legs:
        cm = _get_mission(agency, leg["mission_id"], db)
        _check_mission_state(cm)
        leg_mtype = MissionType(cm.mission_type)
        _require_vehicle_type(leg_mtype, vehicle)
        chain_missions.append(cm)
        if not leg_mtype in (MissionType.INTERCETTAZIONE_TERRESTRE,
                              MissionType.INTERCETTAZIONE_LUNARE,
                              MissionType.EVACUAZIONE):
            leg_fids = leg.get("fighter_ids", [])
            if not leg_fids:
                raise LaunchError(f"tappa {cm.id}: sbarco richiede combattenti")
            leg_fighters = _get_fighters(agency, leg_fids)
            _check_fighters_state(leg_fighters, vehicle)
            chain_fighters_per_leg.append(leg_fighters)
        else:
            chain_fighters_per_leg.append([])

    # calcola ETA
    bp = get_vehicle(vehicle.project)
    is_space = _is_space_mission(mtype)

    if chain_missions:
        all_missions = [mission] + chain_missions
        waypoints = (
            [(agency.base_lat, agency.base_lon)]
            + [(m.target_lat, m.target_lon) for m in all_missions]
            + [(agency.base_lat, agency.base_lon)]
        )
        eta_days = _eta_chain_days(waypoints, bp.velocita)
    else:
        distanza = _haversine_km(
            agency.base_lat, agency.base_lon,
            mission.target_lat, mission.target_lon,
        )
        eta_days = _eta_days(distanza, bp.velocita)

    # overhead lunare (§8.5)
    if is_space:
        eta_days += B.LUNAR_TRANSIT_DAYS

    return_day = current_day + eta_days

    # aggiorna stato prima missione
    mission.status = MissionStatus.IN_PROGRESS.value
    mission.vehicle_id = vehicle_id
    mission.fighters_json = fighter_ids
    mission.sortie_return_day = return_day
    mission.chain_leg = 0

    # aggiorna tappe aggiuntive
    for leg_idx, (cm, leg_fighters) in enumerate(zip(chain_missions, chain_fighters_per_leg)):
        cm.status = MissionStatus.IN_PROGRESS.value
        cm.vehicle_id = vehicle_id
        cm.fighters_json = [f.id for f in leg_fighters]
        cm.sortie_return_day = return_day
        cm.chain_leg = leg_idx + 1

    vehicle.status = "in_flight"
    vehicle.return_day = return_day

    if pilot:
        pilot.status = "in_flight"
    for f in fighters:
        f.status = "in_flight"
    for leg_fighters in chain_fighters_per_leg:
        for f in leg_fighters:
            f.status = "in_flight"

    db.flush()

    return {
        "mission_id": mission_id,
        "vehicle_id": vehicle_id,
        "pilot_id": vehicle.pilot_id,
        "fighters": fighter_ids,
        "chain_legs": len(chain_missions),
        "eta_days": round(eta_days, 2),
        "return_day": round(return_day, 2),
        "mtype": mtype.value,
        "is_space": is_space,
    }
