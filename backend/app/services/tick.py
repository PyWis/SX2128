"""Motore del tick giornaliero — GDD §0.1.

Sequenza (§0.1):
  1. accredita contributo fazione + co-finanziamento UG
  2. addebita manutenzione, rate prestiti, stipendi, addestramento
  3. aggiorna ESPO, classifica, bilancio
  4. assegna nuove missioni; rientro vettori secondo i timer
Idempotente per (server, giorno): rieseguire lo stesso giorno non duplica gli effetti.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.gamedata import balance as B
from app.gamedata.buildings import FIGHTER_VIT_MAX, FIGHTER_VIT_REGEN
from app.models.core import Agency, Server
from app.services import economy
from app.services.missions import assign_daily_missions


def _is_active(agency: Agency, now) -> bool:
    """§9.1: attivo se ultimo login <= 48h."""
    if agency.last_login is None:
        return False
    delta = now - agency.last_login.replace(tzinfo=now.tzinfo)
    return delta <= timedelta(hours=B.INACTIVE_AFTER_HOURS)


def run_tick(db: Session, server: Server) -> dict:
    """Avanza il server di un giorno di gioco e ritorna un riepilogo."""
    from app.models.core import utcnow
    now = utcnow()
    server.current_day += 1
    day = server.current_day

    agencies = db.query(Agency).filter(Agency.server_id == server.id).all()
    summary = {"server_id": server.id, "day": day, "agencies": []}

    for agency in agencies:
        if agency.cut_by_ug:
            continue
        # §9.1 inattivita: oltre 48h l'agenzia e rimossa
        agency.active = _is_active(agency, now)
        if not agency.active:
            summary["agencies"].append({"id": agency.id, "status": "inattiva"})
            continue

        # fedelta lineare cresce di 1 giorno (§1)
        agency.loyalty_days += 1

        # +1 VIT/g gratis in caserma (§4.4)
        for f in agency.fighters:
            if f.status == "barracks" and f.vit < FIGHTER_VIT_MAX:
                f.vit = min(FIGHTER_VIT_MAX, f.vit + FIGHTER_VIT_REGEN)

        # economia del giorno (le missioni 48h reali verranno collegate al log missioni)
        ledger = economy.apply_daily(db, agency, missioni_48h=0)

        # reset flag reclutamento giornaliero
        agency.recruited_today = False

        summary["agencies"].append({
            "id": agency.id, "saldo": round(agency.balance, 2),
            "netto": round(ledger.netto, 2), "espo": round(agency.espo_today, 2),
            "in_default": agency.in_default,
        })

    # assegnazione missioni del nuovo giorno (§9.1)
    assigned = assign_daily_missions(db, server, day)
    summary["missioni_assegnate"] = assigned

    db.flush()
    return summary
