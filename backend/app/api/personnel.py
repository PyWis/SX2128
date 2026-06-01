"""API personale (piloti e combattenti) — GDD §4, §5."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.gamedata.equipment import EQUIPMENT
from app.models.core import Agency, Fighter, Pilot, User
from app.services.hospital_service import HospitalError, discharge, hospitalize
from app.services.training_service import TrainingError, train_fighter_stat, train_pilot_license, train_pilot_stat
from app.services.vehicles_service import VehicleError, equip_fighter

router = APIRouter(prefix="/api/agency", tags=["personnel"])


# --- request bodies ---

class LicenseTrainRequest(BaseModel):
    license_type: str  # "A"/"B"/"C"/"D"/"E"
    tier: str          # "bronze"/"silver"/"gold"/"platinum"


class PilotStatTrainRequest(BaseModel):
    stat: str  # "espo"/"str"/"strs"


class FighterTrainRequest(BaseModel):
    stat: str  # "STR"/"DIF"/"MOV"/"SPA"


class EquipRequest(BaseModel):
    slot: str       # "weapon"/"armor_terra"/"armor_spazio"
    level_key: str  # chiave EQUIPMENT o "" per rimuovere


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


def _pilot_out(p: Pilot) -> dict:
    clean_lic = {k: v for k, v in p.licenses.items() if not k.startswith("__")}
    return {
        "id": p.id, "name": p.name, "origin_culture": p.origin_culture,
        "espo_pct": p.espo_pct, "str_pct": p.str_pct, "strs_pct": p.strs_pct,
        "licenses": clean_lic, "status": p.status,
        "training_until_day": p.training_until_day,
        "training_info": p.training_info,
    }


def _equip_out(f: Fighter) -> dict:
    equip = {}
    for slot in ("weapon", "armor_terra", "armor_spazio"):
        key = getattr(f, f"{slot}_key")
        if key and key in EQUIPMENT:
            eq = EQUIPMENT[key]
            equip[slot] = {"key": key, "livello": eq.livello}
        else:
            equip[slot] = None
    return equip


def _fighter_out(f: Fighter) -> dict:
    return {
        "id": f.id, "name": f.name, "origin_culture": f.origin_culture,
        "vit": f.vit, "str": f.strg, "dif": f.dif, "mov": f.mov, "spa": f.spa,
        "tabi": f.tabi, "missions_completed": f.missions_completed,
        "status": f.status,
        "training_until_day": f.training_until_day,
        "training_stat": f.training_stat,
        "equipment": _equip_out(f),
    }


# --- pilot endpoints ---

@router.get("/{server_id}/pilots")
def list_pilots(server_id: int, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)) -> list:
    agency = _get_agency(db, user, server_id)
    return [_pilot_out(p) for p in agency.pilots if p.status != "eliminated"]


@router.post("/{server_id}/pilots/{pilot_id}/train-license")
def api_train_pilot_license(
    server_id: int, pilot_id: int, payload: LicenseTrainRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> dict:
    agency = _get_agency(db, user, server_id)
    day = _server_day(db, server_id)
    try:
        result = train_pilot_license(db, agency, pilot_id,
                                     payload.license_type, payload.tier, day)
    except TrainingError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return result


@router.post("/{server_id}/pilots/{pilot_id}/train-stat")
def api_train_pilot_stat(
    server_id: int, pilot_id: int, payload: PilotStatTrainRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> dict:
    agency = _get_agency(db, user, server_id)
    day = _server_day(db, server_id)
    try:
        result = train_pilot_stat(db, agency, pilot_id, payload.stat, day)
    except TrainingError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return result


# --- fighter endpoints ---

@router.get("/{server_id}/fighters")
def list_fighters(server_id: int, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> list:
    agency = _get_agency(db, user, server_id)
    return [_fighter_out(f) for f in agency.fighters if f.status != "eliminated"]


@router.post("/{server_id}/fighters/{fighter_id}/train")
def api_train_fighter(
    server_id: int, fighter_id: int, payload: FighterTrainRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> dict:
    agency = _get_agency(db, user, server_id)
    day = _server_day(db, server_id)
    try:
        result = train_fighter_stat(db, agency, fighter_id, payload.stat, day)
    except TrainingError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return result


@router.post("/{server_id}/fighters/{fighter_id}/hospitalize")
def api_hospitalize(
    server_id: int, fighter_id: int,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> dict:
    agency = _get_agency(db, user, server_id)
    try:
        result = hospitalize(db, agency, fighter_id)
    except HospitalError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return result


@router.post("/{server_id}/fighters/{fighter_id}/discharge")
def api_discharge(
    server_id: int, fighter_id: int,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> dict:
    agency = _get_agency(db, user, server_id)
    try:
        result = discharge(db, agency, fighter_id)
    except HospitalError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return result


@router.post("/{server_id}/fighters/{fighter_id}/equip")
def api_equip_fighter(
    server_id: int, fighter_id: int, payload: EquipRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> dict:
    agency = _get_agency(db, user, server_id)
    try:
        result = equip_fighter(db, agency, fighter_id, payload.slot, payload.level_key)
    except VehicleError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return result
