"""Endpoint amministrativi/di sistema: creazione server e avanzamento tick.

In produzione il tick e schedulato da un worker; qui e esposto anche via API
per sviluppo, test e simulazione accelerata.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.core import Server, User
from app.schemas.schemas import ServerCreate
from app.services import monte_carlo, onboarding, tick

router = APIRouter(prefix="/api/admin", tags=["admin"])


class SimRequest(BaseModel):
    pg: float
    pn: float
    n: int = 10_000
    rng_seed: int | None = 42


class BreakevenRequest(BaseModel):
    pn: float
    target_win_rate: float = 0.5
    n: int = 5_000


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


# ─── Monte Carlo (F7 §9.4) ───────────────────────────────────────────────────

@router.post("/montecarlo/simulate")
def mc_simulate(payload: SimRequest,
                user: User = Depends(get_current_user)) -> dict:
    """Simula N combattimenti Pg vs Pn e ritorna statistiche."""
    if payload.pg <= 0 or payload.pn <= 0:
        raise HTTPException(status_code=422, detail="pg e pn devono essere > 0")
    if not (1 <= payload.n <= 200_000):
        raise HTTPException(status_code=422, detail="n deve essere in [1, 200000]")
    return monte_carlo.combat_simulation(payload.pg, payload.pn, payload.n, payload.rng_seed)


@router.post("/montecarlo/breakeven")
def mc_breakeven(payload: BreakevenRequest,
                 user: User = Depends(get_current_user)) -> dict:
    """Trova il Pg di pareggio per il Pn dato."""
    if payload.pn <= 0:
        raise HTTPException(status_code=422, detail="pn deve essere > 0")
    pg = monte_carlo.breakeven_pg(payload.pn, payload.target_win_rate, payload.n)
    return {"pn": payload.pn, "target_win_rate": payload.target_win_rate, "breakeven_pg": pg}


@router.get("/montecarlo/income-band")
def mc_income_band(user: User = Depends(get_current_user)) -> list:
    """Banda di reddito R/g per giorno di gioco (culture campione)."""
    return monte_carlo.income_band_report()


@router.get("/montecarlo/k-luna")
def mc_k_luna(user: User = Depends(get_current_user)) -> dict:
    """Analisi k_luna: confronto win-rate terra vs luna al giorno 60."""
    return monte_carlo.k_luna_analysis(n=10_000)
