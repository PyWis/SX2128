"""Upgrade edifici — GDD §4.1, §5.1, §7."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.gamedata.buildings import (
    BARRACKS_UPGRADES, BARRACKS_MAX,
    HOSPITAL_UPGRADES, HOSPITAL_MAX,
    HANGAR_SLOTS, HANGAR_MAX,
)
from app.gamedata.enums import VehicleClass
from app.models.core import Agency


class BuildingError(Exception):
    pass


def upgrade_barracks(db: Session, agency: Agency) -> dict:
    """§4.1 — sale al prossimo scaglione di capacita caserma."""
    if agency.barracks_capacity >= BARRACKS_MAX:
        raise BuildingError("capacita caserma gia al massimo (100)")
    if agency.in_default:
        raise BuildingError("nessun acquisto in stato di default (§2.3)")

    for (new_cap, cost) in BARRACKS_UPGRADES:
        if agency.barracks_capacity < new_cap:
            if agency.balance < cost:
                raise BuildingError(f"saldo insufficiente (servono {cost} R)")
            agency.balance -= cost
            agency.barracks_capacity = new_cap
            db.flush()
            return {"barracks_capacity": new_cap, "cost": cost}

    raise BuildingError("nessun upgrade disponibile")


def upgrade_hospital(db: Session, agency: Agency) -> dict:
    """§5.1 — sale al prossimo scaglione di capacita ospedale."""
    if agency.hospital_capacity >= HOSPITAL_MAX:
        raise BuildingError("capacita ospedale gia al massimo (25)")
    if agency.in_default:
        raise BuildingError("nessun acquisto in stato di default (§2.3)")

    for (new_cap, cost) in HOSPITAL_UPGRADES:
        if agency.hospital_capacity < new_cap:
            if agency.balance < cost:
                raise BuildingError(f"saldo insufficiente (servono {cost} R)")
            agency.balance -= cost
            agency.hospital_capacity = new_cap
            db.flush()
            return {"hospital_capacity": new_cap, "cost": cost}

    raise BuildingError("nessun upgrade disponibile")


def _prerequisito_ok(agency: Agency, requisito: str | None) -> bool:
    """Verifica se il prerequisito di un slot hangar è soddisfatto."""
    if requisito is None:
        return True
    vclasses = {v.vclass for v in agency.vehicles if v.status != "eliminated"}
    if "caccia" in requisito.lower():
        return VehicleClass.FIGHTER.value in vclasses
    if "spaziale" in requisito.lower():
        return (VehicleClass.SPACE_FIGHTER.value in vclasses
                or VehicleClass.SPACE_MISSION.value in vclasses)
    if "civile" in requisito.lower():
        return VehicleClass.CIVILIAN.value in vclasses
    return True


def upgrade_hangar(db: Session, agency: Agency) -> dict:
    """§7 — sblocca il prossimo slot hangar (con prerequisiti)."""
    if agency.hangar_slots >= HANGAR_MAX:
        raise BuildingError("slot hangar gia al massimo (12)")
    if agency.in_default:
        raise BuildingError("nessun acquisto in stato di default (§2.3)")

    # cerca il prossimo slot da sbloccare
    for slot_spec in HANGAR_SLOTS:
        if slot_spec.slot <= agency.hangar_slots:
            continue
        # è il prossimo
        if not _prerequisito_ok(agency, slot_spec.requisito):
            raise BuildingError(
                f"prerequisito non soddisfatto: {slot_spec.requisito}"
            )
        if agency.balance < slot_spec.cost:
            raise BuildingError(f"saldo insufficiente (servono {slot_spec.cost} R)")
        agency.balance -= slot_spec.cost
        agency.hangar_slots = slot_spec.slot
        db.flush()
        return {"hangar_slots": slot_spec.slot, "cost": slot_spec.cost}

    raise BuildingError("nessun upgrade disponibile")
