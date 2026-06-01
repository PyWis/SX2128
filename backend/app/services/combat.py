"""Risoluzione combattimento — GDD §9.5-9.7, §9.9, §9.11."""
from __future__ import annotations

import random

from app.gamedata import balance as B
from app.gamedata.enums import AlarmLevel, MissionType
from app.gamedata.equipment import EQUIPMENT, MISSILES
from app.gamedata.vehicles import get_vehicle
from app.models.core import Agency, Fighter, Mission, Pilot, Vehicle
from app.services import formulas as F

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
    mtype = MissionType(mission.mission_type)
    is_space = mtype in (MissionType.INTERCETTAZIONE_LUNARE, MissionType.LUNARE)

    if mtype in (MissionType.INTERCETTAZIONE_TERRESTRE, MissionType.INTERCETTAZIONE_LUNARE):
        bp = get_vehicle(vehicle.project)
        missili = _sum_missiles(vehicle, is_space)
        str_pct = (pilot.strs_pct if is_space else pilot.str_pct) if pilot else 0.0
        return F.pg_intercettazione(bp.attacco, missili, str_pct, bp.velocita)

    tabi_list = [_tabi_efficace(f, is_space) for f in fighters]
    return F.pg_sbarco(tabi_list)


def _consume_equipment(fighter: Fighter, rng: random.Random) -> list[str]:
    consumed = []
    for slot in ("weapon_key", "armor_terra_key", "armor_spazio_key"):
        if getattr(fighter, slot) is not None:
            if rng.random() < EQUIP_CONSUME_PROB:
                setattr(fighter, slot, None)
                consumed.append(slot)
    return consumed


def _resolve_evacuazione(
    mission: Mission, vehicle: Vehicle, agency: Agency, rng: random.Random,
    *, is_final_leg: bool = True,
) -> dict:
    """§9.9 — evacuazione civili: nessun combattimento, solo capacità di trasporto."""
    bp = get_vehicle(vehicle.project)
    civili_richiesti = mission.civili_da_salvare or 0
    civili_salvati = min(bp.capacita_h, civili_richiesti)
    ricompensa = round(civili_salvati * B.EVACUAZIONE_TARIFF, 1)
    agency.balance += ricompensa
    agency.missions_completed += 1
    if not agency.first_mission_done:
        agency.first_mission_done = True
        agency.ug_grace_active = False
    if is_final_leg:
        vehicle.status = "barracks"
        vehicle.return_day = None
    return {
        "mission_id": mission.id,
        "mission_type": MissionType.EVACUAZIONE.value,
        "alarm": mission.alarm,
        "pg": 0, "pn": 0, "pg_eff": 0, "pn_eff": 0,
        "success": True,
        "overwhelming": False,
        "ricompensa": ricompensa,
        "losses": [],
        "consumed_equip": [],
        "vehicle_lost": False,
        "pilot_lost": False,
        "civili_salvati": civili_salvati,
    }


def resolve_mission(
    mission: Mission,
    vehicle: Vehicle,
    pilot: Pilot | None,
    fighters: list[Fighter],
    agency: Agency,
    rng: random.Random,
    *,
    is_final_leg: bool = True,
) -> dict:
    """Risolve il combattimento, applica le conseguenze, ritorna il log.

    is_final_leg=False: usato nelle sortie multi-missione (§9.11); sospende il
    rientro del vettore, il consumo equip e il reset missili fino all'ultima tappa.
    """
    mtype = MissionType(mission.mission_type)

    if mtype == MissionType.EVACUAZIONE:
        return _resolve_evacuazione(mission, vehicle, agency, rng, is_final_leg=is_final_leg)

    alarm = AlarmLevel(mission.alarm)
    is_intercept = mtype in (MissionType.INTERCETTAZIONE_TERRESTRE,
                             MissionType.INTERCETTAZIONE_LUNARE)

    pg = _calc_pg(mission, vehicle, pilot, fighters)
    result = F.resolve_combat(pg, mission.pn, rng)
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

    if result.success:
        agency.balance += ricompensa
        agency.missions_completed += 1
        if not agency.first_mission_done:
            agency.first_mission_done = True
            agency.ug_grace_active = False

    if is_intercept and not result.success:
        vehicle.status = "eliminated"
        log["vehicle_lost"] = True
        if pilot:
            pilot.status = "eliminated"
            log["pilot_lost"] = True
            log["losses"].append({"type": "pilot", "name": pilot.name})
    elif is_intercept and result.success and is_final_leg:
        vehicle.status = "barracks"
        vehicle.return_day = None
        if pilot:
            pilot.status = "barracks"
    elif is_intercept and result.success and not is_final_leg:
        if pilot:
            pilot.status = "barracks"   # pilota libero dopo ogni successo

    if not is_intercept and fighters:
        dif_list = [max(1, f.dif) for f in fighters]
        danni = F.ripartisci_danno(result.danno_totale, dif_list)
        for f, danno in zip(fighters, danni):
            f.vit = max(0, int(f.vit - danno))
            if f.vit <= 0:
                f.status = "eliminated"
                log["losses"].append({"type": "fighter", "name": f.name, "vit": 0})
            else:
                if is_final_leg:
                    f.status = "barracks"
                log["losses"].append({"type": "fighter_vit", "name": f.name, "vit": f.vit,
                                      "damage": round(danno, 1)})
            if is_final_leg:
                consumed = _consume_equipment(f, rng)
                if consumed:
                    log["consumed_equip"].append({"fighter": f.name, "slots": consumed})
            f.missions_completed += 1

    if not is_intercept and is_final_leg:
        vehicle.status = "barracks"
        vehicle.return_day = None

    if is_final_leg and vehicle.status != "eliminated":
        vehicle.missiles_terra_count = 0
        vehicle.missiles_terra_key = None
        vehicle.missiles_spazio_count = 0
        vehicle.missiles_spazio_key = None
        vehicle.return_day = None

    return log
