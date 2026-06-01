"""Endpoint amministrativi/di sistema: creazione server e avanzamento tick.

In produzione il tick e schedulato da un worker; qui e esposto anche via API
per sviluppo, test e simulazione accelerata.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.core import Server, User
from app.schemas.schemas import ServerCreate
from app.services import onboarding, tick

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/server")
def create_server(payload: ServerCreate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> dict:
    srv = onboarding.create_server(db, name=payload.name, server_type=payload.server_type)
    db.commit()
    return {"id": srv.id, "name": srv.name, "type": srv.server_type, "day": srv.current_day}


@router.post("/server/{server_id}/tick")
def run_tick(server_id: int, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)) -> dict:
    server = db.get(Server, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="server inesistente")
    summary = tick.run_tick(db, server)
    db.commit()
    return summary
