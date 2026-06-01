"""API Alleanze — GDD §12."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.core import Agency, Alliance, Server, User
from app.services import alliance_service as svc

router = APIRouter(prefix="/api/alliances", tags=["alliances"])


class AllianceCreate(BaseModel):
    server_id: int
    name: str


class TreasuryAction(BaseModel):
    amount: float


class PromoteRequest(BaseModel):
    target_agency_id: int


class TransferMissionRequest(BaseModel):
    mission_id: int


def _my_agency(db: Session, user: User, server_id: int) -> Agency:
    a = db.query(Agency).filter(
        Agency.user_id == user.id, Agency.server_id == server_id,
    ).first()
    if not a:
        raise HTTPException(404, "agenzia non trovata")
    return a


def _alliance_out(al: Alliance, db: Session) -> dict:
    members = db.query(Agency).filter(Agency.alliance_id == al.id).all()
    return {
        "id": al.id,
        "server_id": al.server_id,
        "name": al.name,
        "treasury": round(al.treasury, 2),
        "capo_agency_id": al.capo_agency_id,
        "members": [
            {"id": m.id, "name": m.name, "role": m.alliance_role,
             "missions_completed": m.missions_completed}
            for m in members
        ],
    }


@router.get("/{server_id}")
def list_alliances(server_id: int, db: Session = Depends(get_db),
                   _: User = Depends(get_current_user)) -> list[dict]:
    """Elenca tutte le alleanze del server."""
    server = db.get(Server, server_id)
    if not server:
        raise HTTPException(404, "server non trovato")
    alliances = db.query(Alliance).filter(Alliance.server_id == server_id).all()
    return [_alliance_out(al, db) for al in alliances]


@router.post("")
def create_alliance(payload: AllianceCreate, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)) -> dict:
    agency = _my_agency(db, user, payload.server_id)
    try:
        al = svc.create_alliance(db, agency, payload.name)
    except svc.AllianceError as e:
        raise HTTPException(400, str(e))
    db.commit()
    db.refresh(al)
    return _alliance_out(al, db)


@router.post("/{alliance_id}/join")
def join_alliance(alliance_id: int, server_id: int, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> dict:
    agency = _my_agency(db, user, server_id)
    try:
        al = svc.join_alliance(db, agency, alliance_id)
    except svc.AllianceError as e:
        raise HTTPException(400, str(e))
    db.commit()
    db.refresh(al)
    return _alliance_out(al, db)


@router.delete("/{alliance_id}/leave")
def leave_alliance(alliance_id: int, server_id: int, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)) -> dict:
    agency = _my_agency(db, user, server_id)
    try:
        svc.leave_alliance(db, agency)
    except svc.AllianceError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return {"status": "ok"}


@router.post("/{alliance_id}/treasury/deposit")
def treasury_deposit(alliance_id: int, server_id: int, payload: TreasuryAction,
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    agency = _my_agency(db, user, server_id)
    if agency.alliance_id != alliance_id:
        raise HTTPException(403, "non sei in questa alleanza")
    try:
        al = svc.deposit_treasury(db, agency, payload.amount)
    except svc.AllianceError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return {"treasury": round(al.treasury, 2), "balance": round(agency.balance, 2)}


@router.post("/{alliance_id}/treasury/withdraw")
def treasury_withdraw(alliance_id: int, server_id: int, payload: TreasuryAction,
                      db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    agency = _my_agency(db, user, server_id)
    if agency.alliance_id != alliance_id:
        raise HTTPException(403, "non sei in questa alleanza")
    try:
        al = svc.withdraw_treasury(db, agency, payload.amount)
    except svc.AllianceError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return {"treasury": round(al.treasury, 2), "balance": round(agency.balance, 2)}


@router.post("/{alliance_id}/promote")
def promote_colonnello(alliance_id: int, server_id: int, payload: PromoteRequest,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    agency = _my_agency(db, user, server_id)
    if agency.alliance_id != alliance_id:
        raise HTTPException(403, "non sei in questa alleanza")
    try:
        target = svc.promote_colonnello(db, agency, payload.target_agency_id)
    except svc.AllianceError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return {"agency_id": target.id, "role": target.alliance_role}


@router.post("/{alliance_id}/transfer-mission")
def transfer_mission(alliance_id: int, server_id: int, payload: TransferMissionRequest,
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    agency = _my_agency(db, user, server_id)
    if agency.alliance_id != alliance_id:
        raise HTTPException(403, "non sei in questa alleanza")
    try:
        mission = svc.transfer_mission_to_alliance(db, agency, payload.mission_id)
    except svc.AllianceError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return {
        "mission_id": mission.id,
        "alliance_id": mission.alliance_id,
        "transferred_from_agency_id": mission.transferred_from_agency_id,
    }
