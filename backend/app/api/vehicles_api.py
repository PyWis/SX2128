"""API vettori — GDD §8, §6.2."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.gamedata.equipment import MISSILES
from app.models.core import Agency, User, Vehicle
from app.services.vehicles_service import (
    VehicleError, assign_pilot, buy_vehicle, load_missiles, unassign_pilot,
)

router = APIRouter(prefix="/api/agency", tags=["vehicles"])


# --- request bodies ---

class BuyVehicleRequest(BaseModel):
    project: str


class AssignPilotRequest(BaseModel):
    pilot_id: int


class LoadMissilesRequest(BaseModel):
    missile_key: str   # "bronze"/"silver"/"gold"/"platinum"
    count: int         # 0 = rimuovi
    missile_type: str  # "terra" o "spazio"


# --- helpers ---

def _get_agency(db: Session, user: User, server_id: int) -> Agency:
    a = db.query(Agency).filter(Agency.user_id == user.id,
                                Agency.server_id == server_id).first()
    if not a:
        raise HTTPException(404, "agenzia non trovata")
    return a


def _vehicle_out(v: Vehicle) -> dict:
    missiles = {
        "terra": {"key": v.missiles_terra_key, "count": v.missiles_terra_count},
        "spazio": {"key": v.missiles_spazio_key, "count": v.missiles_spazio_count},
    }
    return {
        "id": v.id, "project": v.project, "vclass": v.vclass,
        "pilot_id": v.pilot_id, "status": v.status,
        "return_day": v.return_day,
        "missiles": missiles,
    }


# --- endpoints ---

@router.get("/{server_id}/vehicles")
def list_vehicles(server_id: int, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> list:
    agency = _get_agency(db, user, server_id)
    return [_vehicle_out(v) for v in agency.vehicles if v.status != "eliminated"]


@router.post("/{server_id}/vehicles/buy")
def api_buy_vehicle(
    server_id: int, payload: BuyVehicleRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> dict:
    agency = _get_agency(db, user, server_id)
    try:
        result = buy_vehicle(db, agency, payload.project)
    except (VehicleError, KeyError) as e:
        raise HTTPException(400, str(e))
    db.commit()
    return result


@router.post("/{server_id}/vehicles/{vehicle_id}/assign-pilot")
def api_assign_pilot(
    server_id: int, vehicle_id: int, payload: AssignPilotRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> dict:
    agency = _get_agency(db, user, server_id)
    try:
        result = assign_pilot(db, agency, vehicle_id, payload.pilot_id)
    except VehicleError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return result


@router.post("/{server_id}/vehicles/{vehicle_id}/unassign-pilot")
def api_unassign_pilot(
    server_id: int, vehicle_id: int,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> dict:
    agency = _get_agency(db, user, server_id)
    try:
        result = unassign_pilot(db, agency, vehicle_id)
    except VehicleError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return result


@router.post("/{server_id}/vehicles/{vehicle_id}/missiles")
def api_load_missiles(
    server_id: int, vehicle_id: int, payload: LoadMissilesRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> dict:
    agency = _get_agency(db, user, server_id)
    try:
        result = load_missiles(
            db, agency, vehicle_id,
            payload.missile_key, payload.count, payload.missile_type,
        )
    except VehicleError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return result
