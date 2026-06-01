"""Flussi economici giornalieri — GDD §2.1, §10, con perk culturali (§1.1)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.gamedata import balance as B
from app.gamedata.buildings import DEFAULT_PENALTY_RATE
from app.gamedata.cultures import get_culture
from app.gamedata.enums import VehicleClass
from app.gamedata.vehicles import get_vehicle
from app.models.core import Agency
from app.services import formulas as F


@dataclass
class DailyLedger:
    contributo: float = 0.0
    cofinanziamento_ug: float = 0.0
    manutenzione: float = 0.0
    rate_prestiti: float = 0.0
    stipendi: float = 0.0
    penale_default: float = 0.0
    dettagli: dict = field(default_factory=dict)

    @property
    def netto(self) -> float:
        return (self.contributo + self.cofinanziamento_ug
                - self.manutenzione - self.rate_prestiti
                - self.stipendi - self.penale_default)


def _is_air(vclass: str) -> bool:
    return vclass in (VehicleClass.EXPLORATION.value, VehicleClass.FIGHTER.value,
                      VehicleClass.MISSION.value)


def compute_espo(agency: Agency) -> float:
    """ESPO/giorno da aerei da esplorazione in hangar con pilota (§8.1) + perk cultura."""
    culture = get_culture(agency.culture)
    pilots = {p.id: p for p in agency.pilots}
    total = 0.0
    for v in agency.vehicles:
        if v.vclass != VehicleClass.EXPLORATION.value:
            continue
        # §8.1: genera ESPO se stazionato (barracks) con pilota operativo assegnato
        if v.status != "barracks" or not v.pilot_id:
            continue
        pilot = pilots.get(v.pilot_id)
        if not pilot or pilot.status in ("eliminated", "in_flight", "training"):
            continue
        bp = get_vehicle(v.project)
        total += bp.espo_giorno * (1 + (pilot.espo_pct or 0.0) / 100.0)
    if "espo_x4" in culture.perks:
        total *= 4
    elif "espo_x2" in culture.perks:
        total *= 2
    return total


def compute_daily(agency: Agency, missioni_48h: int = 0) -> DailyLedger:
    """Calcola il ledger del giorno SENZA applicarlo (puro)."""
    ledger = DailyLedger()
    culture = get_culture(agency.culture)

    # §1 contributo fazione (lineare)
    ledger.contributo = F.contributo_fazione(
        culture.base_r_giorno, culture.fedelta_pct_giorno, agency.loyalty_days
    )
    # perk Africana: +50 R/g per ufficiale (piloti = ufficiali)
    if "income_+50_per_officer" in culture.perks:
        ledger.contributo += 50 * len(agency.pilots)

    # §10 co-finanziamento UG
    ledger.cofinanziamento_ug = F.cofinanziamento_ug(missioni_48h)

    # manutenzione vettori (Pacifica: aerea gratis)
    free_air = "free_air_maintenance" in culture.perks
    for v in agency.vehicles:
        if v.status == "eliminated":
            continue
        bp = get_vehicle(v.project)
        if free_air and _is_air(v.vclass):
            continue
        ledger.manutenzione += bp.maintenance

    # rate prestiti
    for loan in agency.loans:
        if loan.rates_left > 0:
            ledger.rate_prestiti += loan.rate_amount

    # stipendi combattenti (§4.5)
    for f in agency.fighters:
        if f.status == "eliminated":
            continue
        ledger.stipendi += F.stipendio_combattente(f.tabi, f.missions_completed)

    return ledger


def apply_daily(db: Session, agency: Agency, missioni_48h: int = 0) -> DailyLedger:
    """Applica il ledger al saldo, gestisce prestiti, default e ESPO (§2.3)."""
    ledger = compute_daily(agency, missioni_48h)

    # decrementa rate prestiti
    for loan in agency.loans:
        if loan.rates_left > 0:
            loan.rates_left -= 1

    agency.balance += ledger.netto

    # §2.3 default: penale 2%/g sul credito negativo
    if agency.balance < 0:
        agency.in_default = True
        ledger.penale_default = abs(agency.balance) * DEFAULT_PENALTY_RATE
        agency.balance -= ledger.penale_default
    else:
        # esce dal default solo a zero debiti attivi
        if not any(l.rates_left > 0 for l in agency.loans):
            agency.in_default = False

    # ESPO del giorno (pool per la distribuzione missioni del giorno dopo)
    agency.espo_today = compute_espo(agency)
    agency.espo_total += agency.espo_today

    ledger.dettagli = {
        "saldo": round(agency.balance, 2),
        "in_default": agency.in_default,
        "espo_today": round(agency.espo_today, 2),
    }
    return ledger
