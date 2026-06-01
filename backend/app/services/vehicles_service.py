"""Gestione vettori — GDD §8 (acquisto, pilota, missili, equipaggiamento combattenti §6)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.gamedata.cultures import get_culture
from app.gamedata.enums import LicenseTier, LicenseType, VehicleClass
from app.gamedata.equipment import EQUIPMENT, MISSILES, MAX_MISSILES_PER_VEHICLE
from app.gamedata.vehicles import get_vehicle
from app.models.core import Agency, Fighter, Pilot, Vehicle

_TIER_RANK = {
    LicenseTier.BRONZE: 0, LicenseTier.SILVER: 1,
    LicenseTier.GOLD: 2, LicenseTier.PLATINUM: 3,
}

_AIR_CLASSES = {VehicleClass.EXPLORATION.value, VehicleClass.FIGHTER.value, VehicleClass.MISSION.value}
_SPACE_CLASSES = {VehicleClass.SPACE_FIGHTER.value, VehicleClass.SPACE_MISSION.value, VehicleClass.CIVILIAN.value}


class VehicleError(Exception):
    pass


def _active_vehicles(agency: Agency) -> list[Vehicle]:
    return [v for v in agency.vehicles if v.status != "eliminated"]


def _get_vehicle_owned(agency: Agency, vehicle_id: int) -> Vehicle:
    for v in agency.vehicles:
        if v.id == vehicle_id:
            return v
    raise VehicleError("vettore non trovato nell'agenzia")


def _get_pilot(agency: Agency, pilot_id: int) -> Pilot:
    for p in agency.pilots:
        if p.id == pilot_id:
            return p
    raise VehicleError("pilota non trovato nell'agenzia")


def _get_fighter(agency: Agency, fighter_id: int) -> Fighter:
    for f in agency.fighters:
        if f.id == fighter_id:
            return f
    raise VehicleError("combattente non trovato nell'agenzia")


def _pilot_has_license(pilot: Pilot, required: tuple) -> bool:
    """Verifica che il pilota abbia tutte le licenze richieste al tier minimo."""
    for (lt, min_tier) in required:
        owned = pilot.licenses.get(lt.value)
        if owned is None:
            return False
        owned_rank = _TIER_RANK.get(LicenseTier(owned), -1)
        if owned_rank < _TIER_RANK[min_tier]:
            return False
    return True


def buy_vehicle(db: Session, agency: Agency, project: str) -> dict:
    """§8 — acquista un vettore (controlla slot hangar, costo, sconti culturali)."""
    if agency.in_default:
        raise VehicleError("nessun acquisto in stato di default (§2.3)")

    bp = get_vehicle(project)  # solleva KeyError se progetto sconosciuto
    culture = get_culture(agency.culture)

    # controlla slot hangar disponibili
    active = _active_vehicles(agency)
    if len(active) >= agency.hangar_slots:
        raise VehicleError(
            f"hangar pieno ({agency.hangar_slots} slot occupati) — aggiorna l'hangar (§7)"
        )

    # calcola costo con sconti culturali (§1.1)
    cost = bp.cost
    if "aircraft_discount_10_once_day" in culture.perks and bp.vclass.value in _AIR_CLASSES:
        cost = int(cost * 0.90)
    if "spaceplane_discount_20" in culture.perks and bp.vclass.value in _SPACE_CLASSES:
        cost = int(cost * 0.80)

    if agency.balance < cost:
        raise VehicleError(f"saldo insufficiente (servono {cost} R)")

    agency.balance -= cost
    v = Vehicle(
        agency_id=agency.id,
        project=bp.project,
        vclass=bp.vclass.value,
    )
    db.add(v)
    db.flush()
    return {"vehicle_id": v.id, "project": bp.project, "vclass": bp.vclass.value, "cost": cost}


def assign_pilot(db: Session, agency: Agency, vehicle_id: int, pilot_id: int) -> dict:
    """§8 — assegna un pilota a un vettore (controlla licenza e disponibilità)."""
    vehicle = _get_vehicle_owned(agency, vehicle_id)
    pilot = _get_pilot(agency, pilot_id)

    if vehicle.status == "eliminated":
        raise VehicleError("vettore eliminato")
    if vehicle.status == "in_flight":
        raise VehicleError("vettore in volo — impossibile riassegnare")

    if pilot.status == "eliminated":
        raise VehicleError("pilota eliminato")
    if pilot.status == "in_flight":
        raise VehicleError("pilota gia in volo")
    if pilot.status == "training":
        raise VehicleError("pilota in addestramento")

    # verifica licenze
    bp = get_vehicle(vehicle.project)
    # filtra i requisiti escludendo __train_stat (workaround salvataggio stat)
    clean_licenses = {k: v for k, v in pilot.licenses.items() if not k.startswith("__")}
    pilot_with_clean = type("P", (), {"licenses": clean_licenses})()
    if not _pilot_has_license(pilot_with_clean, bp.licenses):
        missing = [(lt.value, tier.value) for lt, tier in bp.licenses]
        raise VehicleError(f"licenze mancanti: {missing}")

    # controlla che il pilota non sia assegnato ad altro vettore attivo
    for v in agency.vehicles:
        if v.id != vehicle_id and v.pilot_id == pilot_id and v.status != "eliminated":
            raise VehicleError("pilota gia assegnato a un altro vettore")

    vehicle.pilot_id = pilot_id
    db.flush()
    return {"vehicle_id": vehicle_id, "pilot_id": pilot_id}


def unassign_pilot(db: Session, agency: Agency, vehicle_id: int) -> dict:
    """Rimuove il pilota assegnato a un vettore."""
    vehicle = _get_vehicle_owned(agency, vehicle_id)
    if vehicle.status == "in_flight":
        raise VehicleError("vettore in volo — impossibile riassegnare")
    vehicle.pilot_id = None
    db.flush()
    return {"vehicle_id": vehicle_id, "pilot_id": None}


def load_missiles(
    db: Session, agency: Agency, vehicle_id: int,
    missile_key: str, count: int, missile_type: str,
) -> dict:
    """§6.2 — carica missili su un vettore da caccia (max 4 totali).

    missile_type: "terra" o "spazio"
    """
    if agency.in_default:
        raise VehicleError("nessun acquisto in stato di default (§2.3)")

    vehicle = _get_vehicle_owned(agency, vehicle_id)
    if vehicle.vclass not in (VehicleClass.FIGHTER.value, VehicleClass.SPACE_FIGHTER.value):
        raise VehicleError("i missili si caricano solo su vettori da caccia (§6.2)")
    if vehicle.status == "in_flight":
        raise VehicleError("vettore in volo")

    if missile_type not in ("terra", "spazio"):
        raise VehicleError("missile_type deve essere 'terra' o 'spazio'")
    if missile_key not in MISSILES:
        raise VehicleError(f"livello missile sconosciuto: {missile_key}")
    if count < 0:
        raise VehicleError("count deve essere >= 0")

    missile = MISSILES[missile_key]

    # calcola totale attuale e nuovo
    current_terra = vehicle.missiles_terra_count
    current_spazio = vehicle.missiles_spazio_count
    if missile_type == "terra":
        new_terra = count
        new_spazio = current_spazio
    else:
        new_terra = current_terra
        new_spazio = count

    if new_terra + new_spazio > MAX_MISSILES_PER_VEHICLE:
        raise VehicleError(f"troppi missili (max {MAX_MISSILES_PER_VEHICLE} totali)")

    # calcola costo dei missili aggiuntivi
    if missile_type == "terra":
        delta = count - current_terra
        cost_per = missile.cost_terra
    else:
        delta = count - current_spazio
        cost_per = missile.cost_spazio

    cost = delta * cost_per if delta > 0 else 0
    if cost > 0 and agency.balance < cost:
        raise VehicleError(f"saldo insufficiente (servono {cost} R)")

    if cost > 0:
        agency.balance -= cost

    if missile_type == "terra":
        vehicle.missiles_terra_key = missile_key if count > 0 else None
        vehicle.missiles_terra_count = count
    else:
        vehicle.missiles_spazio_key = missile_key if count > 0 else None
        vehicle.missiles_spazio_count = count

    db.flush()
    return {
        "vehicle_id": vehicle_id,
        "missiles": {
            "terra": {"key": vehicle.missiles_terra_key, "count": vehicle.missiles_terra_count},
            "spazio": {"key": vehicle.missiles_spazio_key, "count": vehicle.missiles_spazio_count},
        },
        "cost": cost,
    }


def equip_fighter(
    db: Session, agency: Agency, fighter_id: int,
    slot: str, level_key: str,
) -> dict:
    """§6.1 — compra ed equip un'arma/armatura per un combattente.

    slot: "weapon" | "armor_terra" | "armor_spazio"
    level_key: chiave in EQUIPMENT (es. "bronze1")
    """
    if agency.in_default:
        raise VehicleError("nessun acquisto in stato di default (§2.3)")
    if slot not in ("weapon", "armor_terra", "armor_spazio"):
        raise VehicleError("slot non valido (weapon/armor_terra/armor_spazio)")
    if level_key not in EQUIPMENT and level_key != "":
        raise VehicleError(f"livello equipaggiamento sconosciuto: {level_key}")

    fighter = _get_fighter(agency, fighter_id)
    if fighter.status in ("eliminated", "in_flight"):
        raise VehicleError("combattente non disponibile")

    if level_key == "":
        # rimozione equipaggiamento (gratuita)
        setattr(fighter, f"{slot}_key", None)
        db.flush()
        return {"fighter_id": fighter_id, "slot": slot, "level_key": None, "cost": 0}

    equip = EQUIPMENT[level_key]
    if agency.balance < equip.cost:
        raise VehicleError(f"saldo insufficiente (servono {equip.cost} R)")

    agency.balance -= equip.cost
    setattr(fighter, f"{slot}_key", level_key)
    db.flush()
    return {"fighter_id": fighter_id, "slot": slot, "level_key": level_key, "cost": equip.cost}
