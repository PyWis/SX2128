"""Catalogo dati statici di gioco (culture, vettori, equip, prezzi)."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from app.gamedata.buildings import LICENSES, RECRUIT_OPTIONS
from app.gamedata.cultures import CULTURES
from app.gamedata.equipment import EQUIPMENT, MISSILES
from app.gamedata.vehicles import ALL_VEHICLES

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("/cultures")
def cultures() -> list[dict]:
    return [{
        "id": c.id.value, "nome": c.nome, "emoji": c.emoji,
        "base_r_giorno": c.base_r_giorno, "fedelta_pct_giorno": c.fedelta_pct_giorno,
        "vantaggio": c.vantaggio,
    } for c in CULTURES.values()]


@router.get("/vehicles")
def vehicles() -> list[dict]:
    out = []
    for v in ALL_VEHICLES:
        d = asdict(v)
        d["vclass"] = v.vclass.value
        d["licenses"] = [[t.value, tier.value] for (t, tier) in v.licenses]
        out.append(d)
    return out


@router.get("/equipment")
def equipment() -> dict:
    return {
        "equipment": {k: asdict(v) for k, v in EQUIPMENT.items()},
        "missiles": {k: asdict(v) for k, v in MISSILES.items()},
    }


@router.get("/recruit-options")
def recruit_options() -> dict:
    return {k: {"cost": c, "pilots": p, "fighters": f}
            for k, (c, p, f) in RECRUIT_OPTIONS.items()}


@router.get("/licenses")
def licenses() -> dict:
    out: dict = {}
    for ltype, tiers in LICENSES.items():
        out[ltype.value] = {
            tier.value: (None if spec is None else {"cost": spec.cost, "giorni": spec.giorni})
            for tier, spec in tiers.items()
        }
    return out
