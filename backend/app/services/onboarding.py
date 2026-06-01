"""Creazione server e agenzia con stato iniziale — GDD §0.2, §1."""
from __future__ import annotations

import random

from sqlalchemy.orm import Session

from app.gamedata import balance as B
from app.gamedata.buildings import (
    STARTING_BARRACKS, STARTING_CAPITAL, STARTING_HANGAR, STARTING_HOSPITAL,
)
from app.gamedata.cultures import get_culture
from app.gamedata.enums import CultureId, ServerType
from app.models.core import Agency, Server


def create_server(db: Session, name: str, server_type: ServerType = ServerType.F2P) -> Server:
    speed = B.SPEED_CAMPIONI if server_type == ServerType.CAMPIONI else B.SPEED_STANDARD
    srv = Server(name=name, server_type=server_type.value, speed=speed,
                 capacity=256, current_day=0, cycle=1)
    db.add(srv)
    db.flush()
    return srv


def create_agency(db: Session, *, user_id: int, server: Server, name: str,
                  culture: CultureId, base_lat: float, base_lon: float) -> Agency:
    """Stato iniziale (§0.2): 2.000 R, caserma 10, ospedale 2, hangar 3,
    Licenza A-Bronze gratuita, grazia UG attiva."""
    culture_obj = get_culture(culture)
    hangar = STARTING_HANGAR
    # perk Cinese: +2 slot hangar permanenti (§1.1)
    if "hangar_+2" in culture_obj.perks:
        hangar += 2

    agency = Agency(
        user_id=user_id, server_id=server.id, name=name,
        culture=culture.value, loyalty_days=0,
        base_lat=base_lat, base_lon=base_lon,
        balance=STARTING_CAPITAL,
        barracks_capacity=STARTING_BARRACKS,
        hospital_capacity=STARTING_HOSPITAL,
        hangar_slots=hangar,
        ug_grace_active=True, first_mission_done=False,
    )
    db.add(agency)
    db.flush()
    return agency
