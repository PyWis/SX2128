"""Gestione agenzia: creazione, stato, reclutamento."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.core import Agency, Server, User, utcnow
from app.schemas.schemas import AgencyCreate, AgencyOut, RecruitRequest
from app.services import onboarding, recruitment

router = APIRouter(prefix="/api/agency", tags=["agency"])


@router.post("", response_model=AgencyOut)
def create_agency(payload: AgencyCreate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> Agency:
    server = db.get(Server, payload.server_id)
    if not server:
        raise HTTPException(status_code=404, detail="server inesistente")
    if db.query(Agency).filter(Agency.user_id == user.id,
                               Agency.server_id == server.id).first():
        raise HTTPException(status_code=400, detail="hai gia un'agenzia su questo server")
    count = db.query(Agency).filter(Agency.server_id == server.id).count()
    if count >= server.capacity:
        raise HTTPException(status_code=400, detail="server al completo (256 agenzie)")
    agency = onboarding.create_agency(
        db, user_id=user.id, server=server, name=payload.name,
        culture=payload.culture, base_lat=payload.base_lat, base_lon=payload.base_lon,
    )
    db.commit()
    db.refresh(agency)
    return agency


def _get_my_agency(db: Session, user: User, server_id: int) -> Agency:
    agency = db.query(Agency).filter(Agency.user_id == user.id,
                                     Agency.server_id == server_id).first()
    if not agency:
        raise HTTPException(status_code=404, detail="agenzia non trovata")
    return agency


@router.get("/{server_id}", response_model=AgencyOut)
def get_agency(server_id: int, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)) -> Agency:
    agency = _get_my_agency(db, user, server_id)
    agency.last_login = utcnow()  # §9.1 marca attivita
    db.commit()
    return agency


@router.post("/{server_id}/recruit")
def recruit(server_id: int, payload: RecruitRequest, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)) -> dict:
    agency = _get_my_agency(db, user, server_id)
    try:
        result = recruitment.recruit(db, agency, payload.option)
    except recruitment.RecruitError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return result
