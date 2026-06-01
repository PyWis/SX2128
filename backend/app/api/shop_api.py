"""API Shop — GDD §6 / doc Shop."""
from __future__ import annotations

import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.core import Agency, Server, User
from app.services import shop_service as svc

router = APIRouter(prefix="/api/shop", tags=["shop"])


class PurchaseRequest(BaseModel):
    server_id: int
    package_key: str


class RedeemRequest(BaseModel):
    unit_type: str  # "pilot" | "fighter" | "vehicle"


def _my_agency(db: Session, user: User, server_id: int) -> Agency:
    a = db.query(Agency).filter(
        Agency.user_id == user.id, Agency.server_id == server_id,
    ).first()
    if not a:
        raise HTTPException(404, "agenzia non trovata")
    return a


@router.get("/catalog")
def catalog(_: User = Depends(get_current_user)) -> list[dict]:
    """Catalogo pacchetti shop con prezzi e contenuto."""
    return svc.get_catalog()


@router.post("/purchase")
def purchase(payload: PurchaseRequest, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)) -> dict:
    """Acquista un pacchetto shop (anti-P2W: max 1/ciclo, max 1/giorno)."""
    agency = _my_agency(db, user, payload.server_id)
    server = db.get(Server, payload.server_id)
    if not server:
        raise HTTPException(404, "server non trovato")
    try:
        tx = svc.purchase(db, agency, server, payload.package_key)
    except svc.ShopError as e:
        raise HTTPException(400, str(e))
    db.commit()
    pool = agency.premium_pool_json or []
    return {
        "transaction_id": tx.id,
        "package_key": tx.package_key,
        "price_eur": tx.price_eur,
        "agenda_2030_eur": tx.agenda_2030_eur,
        "cycle": tx.cycle_at_purchase,
        "pool_size": len(pool),
        "pool_summary": _pool_summary(pool),
    }


@router.post("/{server_id}/redeem")
def redeem(server_id: int, payload: RedeemRequest, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)) -> dict:
    """Riscatta 1 unità dal Pool di Riserva Premium."""
    agency = _my_agency(db, user, server_id)
    try:
        result = svc.redeem_from_pool(db, agency, payload.unit_type, random.Random())
    except svc.ShopError as e:
        raise HTTPException(400, str(e))
    db.commit()
    pool = agency.premium_pool_json or []
    result["pool_remaining"] = len(pool)
    return result


@router.get("/{server_id}/pool")
def get_pool(server_id: int, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)) -> dict:
    """Mostra il contenuto del Pool di Riserva Premium."""
    agency = _my_agency(db, user, server_id)
    pool = agency.premium_pool_json or []
    return {"pool_size": len(pool), "pool": _pool_summary(pool)}


@router.get("/{server_id}/transactions")
def transactions(server_id: int, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)) -> list[dict]:
    """Storico acquisti con tracciabilità Agenda 2030."""
    agency = _my_agency(db, user, server_id)
    return svc.get_transactions(db, agency.id)


def _pool_summary(pool: list[dict]) -> dict:
    summary: dict[str, int] = {}
    for u in pool:
        k = u.get("unit_type", "unknown")
        summary[k] = summary.get(k, 0) + 1
    return summary
