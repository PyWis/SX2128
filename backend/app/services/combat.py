"""Risoluzione combattimento — GDD §9.5-9.7.

Calcola Pg in base al tipo di missione, risolve il combattimento e
applica le conseguenze (danni, premi, perdite strutturali) ai modelli.
"""
from __future__ import annotations

import random

from app.gamedata.enums import AlarmLevel, MissionType, VehicleClass
from app.gamedata.equipment import EQUIPMENT, MISSILES
from app.gamedata.vehicles import get_vehicle
from app.models.core import Agency, Fighter, Mission, Pilot, Vehicle
from app.services import formulas as F

# consumo equipaggiamento al rientro (§6)
EQUIP_CONSUME_PROB = 0.30


def _tabi_efficace(fighter: Fighter, is_space: bool) -> int:
    """TABI con effetti equipaggiamento (§6.1)."""
    strg = fighter.strg
    dif = fighter.dif
    mov = fighter.mov
    spa = fighter.spa

    if fighter.weapon_key and fighter.weapon_key in EQUIPMENT:
        eq = EQUIPMENT[fighter.weapon_key]
        strg += eq.arma_str
        mov += eq.arma_mov

    if not is_space and fighter.armor_terra_key and fighter.armor_terra_key in EQUIPMENT:
        eq = EQUIPMENT[fighter.armor_terra_key]
        dif += eq.terra_dif
        mov += eq.terra_mov
    elif is_space and fighter.armor_spazio_key and fighter.armor_spazio_key in EQUIPMENT:
        eq = EQUIPMENT[fighter.armor_spazio_key]
        dif += eq.spazio_dif
        spa += eq.spazio_spa

    return max(0, strg) + max(0, dif) + max(0, mov) + max(0, spa)


def _sum_missiles(vehicle: Vehicle, is_space: bool) -> int:
    """Somma potenza missili del vettore (terra STR o spazio STRS)."""
    total = 0
    if not is_space and vehicle.missiles_terra_key and vehicle.missiles_terra_key in MISSILES:
        total += MISSILES[vehicle.missiles_terra_key].str_terra * vehicle.missiles_terra_count
    if is_space and vehicle.missiles_spazio_key and vehicle.missiles_spazio_key in MISSILES:
        total += MISSILES[vehicle.missiles_spazio_key].strs_spazio * vehicle.missiles_spazio_count
    return total


def _calc_pg(
    mission: Mission, vehicle: Vehicle, pilot: Pilot | None,
    fighters: list[Fighter],
) -> float:
    """Calcola Pg in base al tipo di missione."""
    mtype = MissionType(mission.mission_type)
    is_space = mtype in (MissionType.INTERCETTAZIONE_LUNARE, MissionType.LUNARE)

    if mtype in (MissionType.INTERCETTAZIONE_TERRESTRE, MissionType.INTERCETTAZIONE_LUNARE):
        bp = get_vehicle(vehicle.project)
        missili = _sum_missiles(vehicle, is_space)
        str_pct = (pilot.strs_pct if is_space else pilot.str_pct) if pilot else 0.0
        return F.pg_intercettazione(bp.attacco, missili, str_pct, bp.velocita)

    # sbarco (Terrestre / Lunare)
    tabi_list = [_tabi_efficace(f, is_space) for f in fighters]
    return F.pg_sbarco(tabi_list)


def _consume_equipment(fighter: Fighter, rng: random.Random) -> list[str]:
    """§6 — 30% di probabilità di perdere ogni pezzo di equipaggiamento."""
    consumed = []
    for slot in ("weapon_key", "armor_terra_key", "armor_spazio_key"):
        if getattr(fighter, slot) is not None:
            if rng.random() < EQUIP_CONSUME_PROB:
                setattr(fighter, slot, None)
                consumed.append(slot)
    return consumed


def resolve_mission(
    mission: Mission,
    vehicle: Vehicle,
    pilot: Pilot | None,
    fighters: list[Fighter],
    agency: Agency,
    rng: random.Random,
) -> dict:
    """Risolve il combattimento, applica le conseguenze, ritorna il log.

    Effetti applicati:
    - Saldo agency += ricompensa (se successo)
    - missions_completed += 1 (se successo)
    - first_mission_done = True (se era la prima)
    - ug_grace_active = False (dopo la prima missione)
    - Danni ai combattenti: VIT ridotto; se VIT<=0 → eliminato
    - Intercettazione: su sconfitta vettore + pilota eliminati
    - Equipaggiamento: 30% consumo per combattente al rientro
    - Missili vettore: azzerati al rientro
    - Unità: status → barracks
    """
    mtype = MissionType(mission.mission_type)
    alarm = AlarmLevel(mission.alarm)
    is_intercept = mtype in (MissionType.INTERCETTAZIONE_TERRESTRE,
                             MissionType.INTERCETTAZIONE_LUNARE)

    pg = _calc_pg(mission, vehicle, pilot, fighters)
    result = F.resolve_combat(pg, mission.pn, rng)

    # ricompensa (§9.7) — calcolata su Pn reale della missione
    ricompensa = F.reward(mission.pn, mtype, alarm) if result.success else 0.0

    log: dict = {
        "mission_id": mission.id,
        "mission_type": mtype.value,
        "alarm": alarm.value,
        "pg": round(pg, 1),
        "pn": round(mission.pn, 1),
        "pg_eff": round(result.pg_eff, 1),
        "pn_eff": round(result.pn_eff, 1),
        "success": result.success,
        "overwhelming": result.overwhelming,
        "ricompensa": round(ricompensa, 1),
        "losses": [],
        "consumed_equip": [],
        "vehicle_lost": False,
        "pilot_lost": False,
    }

    # applica conseguenze
    if result.success:
        agency.balance += ricompensa
        agency.missions_completed += 1
        if not agency.first_mission_done:
            agency.first_mission_done = True
            agency.ug_grace_active = False

    if is_intercept and not result.success:
        # §9.6: distruzione vettore + morte pilota su sconfitta
        vehicle.status = "eliminated"
        log["vehicle_lost"] = True
        if pilot:
            pilot.status = "eliminated"
            log["pilot_lost"] = True
            log["losses"].append({"type": "pilot", "name": pilot.name})
    elif is_intercept:
        # vettore torna in hangar, pilota libero
        vehicle.status = "barracks"
        vehicle.return_day = None

    # sbarco: danni ai combattenti
    if not is_intercept and fighters:
        dif_list = [max(1, f.dif) for f in fighters]
        danni = F.ripartisci_danno(result.danno_totale, dif_list)
        for f, danno in zip(fighters, danni):
            f.vit = max(0, int(f.vit - danno))
            if f.vit <= 0:
                f.status = "eliminated"
                log["losses"].append({"type": "fighter", "name": f.name, "vit": 0})
            else:
                f.status = "barracks"
                log["losses"].append({"type": "fighter_vit", "name": f.name, "vit": f.vit,
                                      "damage": round(danno, 1)})
            # consumo equipaggiamento (§6)
            consumed = _consume_equipment(f, rng)
            if consumed:
                log["consumed_equip"].append({"fighter": f.name, "slots": consumed})
            f.missions_completed += 1
    elif is_intercept and result.success:
        # pilota aggiorna conteggio missioni
        if pilot:
            pilot.status = "barracks"

    # sbarco: vettore torna in hangar (non eliminato nelle missioni terrestri/lunari)
    if not is_intercept:
        vehicle.status = "barracks"
        vehicle.return_day = None

    # missili vettore azzerati al rientro (§6.2)
    if vehicle.status != "eliminated":
        vehicle.missiles_terra_count = 0
        vehicle.missiles_terra_key = None
        vehicle.missiles_spazio_count = 0
        vehicle.missiles_spazio_key = None
        vehicle.return_day = None

    return log
