"""API upgrade edifici — GDD §4.1, §5.1, §7."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.core import User
from app.services.buildings_service import BuildingError, upgrade_barracks, upgrade_hangar, upgrade_hospital

router = APIRouter(prefix="/api/agency", tags=["buildings"])


def _get_agency(db, user, server_id):
    from app.models.core import Agency
    a = db.query(Agency).filter(Agency.user_id == user.id,
                                Agency.server_id == server_id).first()
    if not a:
        raise HTTPException(404, "agenzia non trovata")
    return a


@router.post("/{server_id}/buildings/barracks/upgrade")
def api_upgrade_barracks(server_id: int, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)) -> dict:
    agency = _get_agency(db, user, server_id)
    try:
        result = upgrade_barracks(db, agency)
    except BuildingError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return result


@router.post("/{server_id}/buildings/hospital/upgrade")
def api_upgrade_hospital(server_id: int, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)) -> dict:
    agency = _get_agency(db, user, server_id)
    try:
        result = upgrade_hospital(db, agency)
    except BuildingError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return result


@router.post("/{server_id}/buildings/hangar/upgrade")
def api_upgrade_hangar(server_id: int, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)) -> dict:
    agency = _get_agency(db, user, server_id)
    try:
        result = upgrade_hangar(db, agency)
    except BuildingError as e:
        raise HTTPException(400, str(e))
    db.commit()
    return result
