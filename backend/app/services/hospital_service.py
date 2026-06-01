"""Ospedale — GDD §5."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.core import Agency, Fighter


class HospitalError(Exception):
    pass


def _get_fighter(agency: Agency, fighter_id: int) -> Fighter:
    for f in agency.fighters:
        if f.id == fighter_id:
            return f
    raise HospitalError("combattente non trovato nell'agenzia")


def hospitalize(db: Session, agency: Agency, fighter_id: int) -> dict:
    """§5.1 — assegna un combattente a un letto ospedale (status barracks → hospital)."""
    fighter = _get_fighter(agency, fighter_id)

    if fighter.status == "eliminated":
        raise HospitalError("combattente eliminato")
    if fighter.status in ("in_flight", "training"):
        raise HospitalError("combattente non disponibile")
    if fighter.status == "hospital":
        raise HospitalError("combattente gia in ospedale")
    if fighter.vit >= 100:
        raise HospitalError("combattente gia a piena salute (VIT 100)")

    # conta i letti occupati
    beds_in_use = sum(1 for f in agency.fighters if f.status == "hospital")
    if beds_in_use >= agency.hospital_capacity:
        raise HospitalError(
            f"ospedale al completo ({agency.hospital_capacity} letti occupati)"
        )

    fighter.status = "hospital"
    db.flush()
    return {"fighter_id": fighter.id, "name": fighter.name, "vit": fighter.vit}


def discharge(db: Session, agency: Agency, fighter_id: int) -> dict:
    """Dimette un combattente dall'ospedale."""
    fighter = _get_fighter(agency, fighter_id)

    if fighter.status != "hospital":
        raise HospitalError("combattente non in ospedale")

    fighter.status = "barracks"
    db.flush()
    return {"fighter_id": fighter.id, "name": fighter.name, "vit": fighter.vit}
