"""Centro Reclute — GDD §3 (con perk culturali §1.1)."""
from __future__ import annotations

import random

from sqlalchemy.orm import Session

from app.gamedata.buildings import RECRUIT_OPTIONS
from app.gamedata.cultures import get_culture
from app.gamedata.enums import CultureId
from app.models.core import Agency, Fighter, Pilot
from app.services import formulas as F
from app.services.names import generate_name


class RecruitError(Exception):
    pass


def _count_units(agency: Agency) -> int:
    alive_p = [p for p in agency.pilots if p.status != "eliminated"]
    alive_f = [f for f in agency.fighters if f.status != "eliminated"]
    return len(alive_p) + len(alive_f)


def recruit(db: Session, agency: Agency, option: str, rng: random.Random | None = None) -> dict:
    """Esegue un reclutamento (max 1/giorno, §3). Ritorna le unita create."""
    rng = rng or random.Random()
    if option not in RECRUIT_OPTIONS:
        raise RecruitError(f"opzione sconosciuta: {option}")
    if agency.recruited_today:
        raise RecruitError("reclutamento gia effettuato oggi (max 1/giorno, §3)")
    if agency.in_default:
        raise RecruitError("nessun acquisto possibile in stato di default (§2.3)")

    cost, n_pilots, n_fighters = RECRUIT_OPTIONS[option]
    culture = get_culture(agency.culture)

    # capacita caserma (§4)
    if _count_units(agency) + n_pilots + n_fighters > agency.barracks_capacity:
        raise RecruitError("capacita caserma insufficiente (§4)")
    if agency.balance < cost:
        raise RecruitError("saldo insufficiente")

    agency.balance -= cost
    created_pilots, created_fighters = [], []

    for _ in range(n_pilots):
        name, origin = generate_name(CultureId(agency.culture), rng)
        licenses = {}
        if "native_d_bronze" in culture.perks:  # Lunare
            licenses["D"] = "bronze"
        p = Pilot(
            agency_id=agency.id, name=name, origin_culture=origin.value,
            espo_pct=F.roll_pilot_stat(rng),
            str_pct=F.roll_pilot_stat(rng),
            strs_pct=F.roll_pilot_stat(rng),
            licenses=licenses,
        )
        db.add(p)
        created_pilots.append(p)

    for _ in range(n_fighters):
        name, origin = generate_name(CultureId(agency.culture), rng)
        stats = F.roll_fighter_stats(rng)
        strv = stats["STR"]
        # perk Non Tecnologica: STR nativi +30% (§1.1)
        if "native_str_+30" in culture.perks and origin.value == agency.culture:
            strv = int(round(strv * 1.3))
        f = Fighter(
            agency_id=agency.id, name=name, origin_culture=origin.value,
            vit=stats["VIT"], strg=strv, dif=stats["DIF"],
            mov=stats["MOV"], spa=stats["SPA"],
        )
        db.add(f)
        created_fighters.append(f)

    agency.recruited_today = True
    db.flush()
    return {
        "cost": cost,
        "pilots": [{"id": p.id, "name": p.name} for p in created_pilots],
        "fighters": [{"id": f.id, "name": f.name, "tabi": f.tabi} for f in created_fighters],
    }
