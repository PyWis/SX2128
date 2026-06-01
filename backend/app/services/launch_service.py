"""Lancio di una missione — GDD §9.10, §8."""
from __future__ import annotations

import math

from sqlalchemy.orm import Session

from app.gamedata.enums import MissionStatus, MissionType, VehicleClass
from app.gamedata.vehicles import get_vehicle
from app.models.core import Agency, Fighter, Mission, Pilot, Vehicle

MACH_KMH = 1235.0  # 1 Mach in km/h (velocità approssimata a livello del mare)


class LaunchError(Exception):
    pass


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distanza geodetica in km tra due punti lat/lon."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _eta_days(distanza_km: float, velocita: float) -> float:
    """ETA in giorni di gioco: andata + ritorno (2 × distanza / velocità)."""
    if velocita <= 0:
        return 1.0
    ore = (2 * distanza_km) / (velocita * MACH_KMH)
    return max(1.0, ore / 24.0)


def _get_mission(agency: Agency, mission_id: int, db: Session) -> Mission:
    m = db.query(Mission).filter(
        Mission.id == mission_id, Mission.agency_id == agency.id
    ).first()
    if not m:
        raise LaunchError("missione non trovata o non assegnata all'agenzia")
    return m


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
    """Valida che il tipo di vettore sia compatibile con il tipo di missione (§9.3)."""
    vclass = vehicle.vclass
    if mission_type == MissionType.TERRESTRE:
        allowed = {VehicleClass.MISSION.value}
    elif mission_type == MissionType.INTERCETTAZIONE_TERRESTRE:
        allowed = {VehicleClass.FIGHTER.value}
    elif mission_type == MissionType.INTERCETTAZIONE_LUNARE:
        allowed = {VehicleClass.SPACE_FIGHTER.value}
    elif mission_type == MissionType.LUNARE:
        allowed = {VehicleClass.SPACE_MISSION.value}
    else:
        return  # UG / Evacuazione: gestite in F4/F5

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
) -> dict:
    """Lancia una missione: valida il loadout, calcola ETA, mette in volo.

    - Per Intercettazione (TERRESTRE / LUNARE): il vettore deve avere un pilota assegnato.
    - Per Sbarco (TERRESTRE / LUNARE): il vettore da missione trasporta i combattenti.
    - L'ETA è 2 × distanza_km / (velocità × MACH_KMH / 24h).
    """
    mission = _get_mission(agency, mission_id, db)
    _check_mission_state(mission)

    vehicle = _get_vehicle(agency, vehicle_id)
    _check_vehicle_state(vehicle)

    mtype = MissionType(mission.mission_type)
    _require_vehicle_type(mtype, vehicle)

    is_intercept = mtype in (MissionType.INTERCETTAZIONE_TERRESTRE,
                              MissionType.INTERCETTAZIONE_LUNARE)

    # per le intercettazioni serve un pilota con licenza adeguata
    pilot: Pilot | None = None
    if is_intercept:
        if not vehicle.pilot_id:
            raise LaunchError("nessun pilota assegnato al vettore (§8)")
        pilot = next((p for p in agency.pilots if p.id == vehicle.pilot_id), None)
        if not pilot or pilot.status in ("eliminated", "training"):
            raise LaunchError("pilota non disponibile")

    # per sbarco serve almeno 1 combattente
    fighters: list[Fighter] = []
    if not is_intercept:
        if not fighter_ids:
            raise LaunchError("sbarco richiede almeno 1 combattente")
        fighters = _get_fighters(agency, fighter_ids)
        _check_fighters_state(fighters, vehicle)

    # calcola ETA (§8)
    bp = get_vehicle(vehicle.project)
    distanza = _haversine_km(
        agency.base_lat, agency.base_lon,
        mission.target_lat, mission.target_lon,
    )
    eta_days = _eta_days(distanza, bp.velocita)
    return_day = current_day + eta_days

    # aggiorna stato
    mission.status = MissionStatus.IN_PROGRESS.value
    mission.vehicle_id = vehicle_id
    mission.fighters_json = fighter_ids
    mission.sortie_return_day = return_day

    vehicle.status = "in_flight"
    vehicle.return_day = return_day

    if pilot:
        pilot.status = "in_flight"
    for f in fighters:
        f.status = "in_flight"

    db.flush()

    return {
        "mission_id": mission_id,
        "vehicle_id": vehicle_id,
        "pilot_id": vehicle.pilot_id,
        "fighters": fighter_ids,
        "distanza_km": round(distanza, 1),
        "eta_days": round(eta_days, 2),
        "return_day": round(return_day, 2),
        "mtype": mtype.value,
    }
