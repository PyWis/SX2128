"""Classifica del server — GDD §11."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.core import Agency, Server, User

router = APIRouter(prefix="/api/classifica", tags=["classifica"])


@router.get("/{server_id}")
def get_classifica(server_id: int, db: Session = Depends(get_db),
                   _: User = Depends(get_current_user)) -> list[dict]:
    """Classifica agenzie per missioni completate; spareggio ESPO totale (§11)."""
    server = db.get(Server, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="server non trovato")

    agencies = db.query(Agency).filter(
        Agency.server_id == server_id,
        Agency.cut_by_ug == False,   # noqa: E712
    ).all()

    ranked = sorted(
        agencies,
        key=lambda a: (a.missions_completed, a.espo_total),
        reverse=True,
    )

    return [
        {
            "rank": i + 1,
            "agency_id": a.id,
            "name": a.name,
            "culture": a.culture,
            "missions_completed": a.missions_completed,
            "espo_total": round(a.espo_total, 2),
            "balance": round(a.balance, 2),
            "alliance_id": a.alliance_id,
            "alliance_role": a.alliance_role,
            "active": a.active,
        }
        for i, a in enumerate(ranked)
    ]
