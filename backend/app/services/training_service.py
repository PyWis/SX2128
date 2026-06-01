"""Addestramento piloti e combattenti — GDD §4.2, §4.3, §4.4."""
from __future__ import annotations

import math

from sqlalchemy.orm import Session

from app.gamedata.buildings import (
    LICENSES, PILOT_TRAIN_COST, PILOT_TRAIN_CAP,
    FIGHTER_TRAIN_COST, FIGHTER_LIMITS,
)
from app.gamedata.cultures import get_culture
from app.gamedata.enums import LicenseTier, LicenseType
from app.models.core import Agency, Fighter, Pilot

_TIER_ORDER = [LicenseTier.BRONZE, LicenseTier.SILVER, LicenseTier.GOLD, LicenseTier.PLATINUM]
_TIER_RANK = {t: i for i, t in enumerate(_TIER_ORDER)}


class TrainingError(Exception):
    pass


def _get_pilot(agency: Agency, pilot_id: int) -> Pilot:
    for p in agency.pilots:
        if p.id == pilot_id:
            return p
    raise TrainingError("pilota non trovato nell'agenzia")


def _get_fighter(agency: Agency, fighter_id: int) -> Fighter:
    for f in agency.fighters:
        if f.id == fighter_id:
            return f
    raise TrainingError("combattente non trovato nell'agenzia")


def train_pilot_license(
    db: Session, agency: Agency, pilot_id: int,
    license_type: str, tier: str, current_day: int,
) -> dict:
    """§4.2 — avvia addestramento licenza pilota.

    Regole:
    - Il pilota deve essere in caserma (non in volo, non eliminato, non in training).
    - Deve possedere il tier precedente (bronze prima di silver, ecc.).
    - Costo e durata da LICENSES; perk Europea -25% durata.
    - Al completamento (gestito dal tick) la licenza viene assegnata.
    """
    if agency.in_default:
        raise TrainingError("nessun acquisto in stato di default (§2.3)")

    pilot = _get_pilot(agency, pilot_id)
    if pilot.status == "eliminated":
        raise TrainingError("pilota eliminato")
    if pilot.status == "in_flight":
        raise TrainingError("pilota non disponibile (in volo)")
    if pilot.status == "training":
        raise TrainingError("pilota gia in addestramento")

    try:
        lt = LicenseType(license_type)
        tr = LicenseTier(tier)
    except ValueError:
        raise TrainingError("tipo o tier licenza non valido")

    spec = LICENSES.get(lt, {}).get(tr)
    if spec is None:
        raise TrainingError("combinazione licenza non disponibile")

    # verifica progressione: deve possedere il tier precedente (se non è bronze)
    rank = _TIER_RANK[tr]
    if rank > 0:
        prev_tier = _TIER_ORDER[rank - 1]
        owned_tier = pilot.licenses.get(lt.value)
        if owned_tier != prev_tier.value:
            raise TrainingError(
                f"occorre prima la licenza {lt.value.upper()}-{prev_tier.value} (§4.2)"
            )
    else:
        # bronze: non ripetere se già posseduta o superiore
        owned = pilot.licenses.get(lt.value)
        if owned is not None and _TIER_RANK.get(LicenseTier(owned), 0) >= rank:
            raise TrainingError("licenza gia posseduta o superiore")

    if agency.balance < spec.cost:
        raise TrainingError(f"saldo insufficiente (servono {spec.cost} R)")

    # calcola durata con perk Europea (-25%)
    culture = get_culture(agency.culture)
    giorni = spec.giorni
    if "license_time_-25" in culture.perks:
        giorni = max(1, math.ceil(giorni * 0.75))

    agency.balance -= spec.cost
    pilot.status = "training"
    pilot.training_until_day = current_day + giorni
    # training_info: "lic:<type>:<tier>"
    pilot.training_info = f"lic:{lt.value}:{tr.value}"
    db.flush()

    return {
        "pilot_id": pilot.id,
        "license_type": lt.value,
        "tier": tr.value,
        "cost": spec.cost,
        "giorni_addestramento": giorni,
        "completamento_giorno": pilot.training_until_day,
    }


def train_pilot_stat(
    db: Session, agency: Agency, pilot_id: int,
    stat: str, current_day: int,
) -> dict:
    """§4.3 — addestramento stat pilota (+1%, 1 giorno, cap 25%)."""
    if agency.in_default:
        raise TrainingError("nessun acquisto in stato di default (§2.3)")
    if stat not in ("espo", "str", "strs"):
        raise TrainingError("stat non valida (espo/str/strs)")

    pilot = _get_pilot(agency, pilot_id)
    if pilot.status in ("eliminated", "in_flight", "training"):
        raise TrainingError("pilota non disponibile")

    current_val = getattr(pilot, f"{stat}_pct")
    if current_val >= PILOT_TRAIN_CAP:
        raise TrainingError(f"stat {stat} gia al cap ({PILOT_TRAIN_CAP}%)")

    if agency.balance < PILOT_TRAIN_COST:
        raise TrainingError(f"saldo insufficiente (servono {PILOT_TRAIN_COST} R)")

    agency.balance -= PILOT_TRAIN_COST
    pilot.status = "training"
    pilot.training_until_day = current_day + 1
    pilot.training_info = f"stat:{stat}"
    db.flush()

    return {
        "pilot_id": pilot.id,
        "stat": stat,
        "current_pct": current_val,
        "new_pct_at_completion": round(current_val + 1.0, 1),
        "completamento_giorno": current_day + 1,
    }


def train_fighter_stat(
    db: Session, agency: Agency, fighter_id: int,
    stat: str, current_day: int,
) -> dict:
    """§4.4 — addestramento stat combattente (+1 punto, 1 giorno)."""
    if agency.in_default:
        raise TrainingError("nessun acquisto in stato di default (§2.3)")
    if stat not in ("STR", "DIF", "MOV", "SPA"):
        raise TrainingError("stat non valida (STR/DIF/MOV/SPA)")

    fighter = _get_fighter(agency, fighter_id)
    if fighter.status in ("eliminated", "in_flight", "training"):
        raise TrainingError("combattente non disponibile")

    cap = FIGHTER_LIMITS[stat]
    stat_map = {"STR": "strg", "DIF": "dif", "MOV": "mov", "SPA": "spa"}
    attr = stat_map[stat]
    current_val = getattr(fighter, attr)

    if current_val >= cap:
        raise TrainingError(f"stat {stat} gia al cap ({cap})")

    if agency.balance < FIGHTER_TRAIN_COST:
        raise TrainingError(f"saldo insufficiente (servono {FIGHTER_TRAIN_COST} R)")

    agency.balance -= FIGHTER_TRAIN_COST
    fighter.status = "training"
    fighter.training_until_day = current_day + 1
    fighter.training_stat = stat
    db.flush()

    return {
        "fighter_id": fighter.id,
        "stat": stat,
        "current_val": current_val,
        "new_val_at_completion": current_val + 1,
        "completamento_giorno": current_day + 1,
    }
