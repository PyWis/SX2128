"""Gestione alleanze — GDD §12."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.gamedata import balance as B
from app.gamedata.enums import AllianceRole
from app.models.core import Agency, Alliance


class AllianceError(ValueError):
    pass


def create_alliance(db: Session, agency: Agency, name: str) -> Alliance:
    if agency.alliance_id:
        raise AllianceError("sei gia in un'alleanza")
    name = name.strip()
    if not name:
        raise AllianceError("nome alleanza non valido")
    existing = db.query(Alliance).filter(
        Alliance.server_id == agency.server_id,
        Alliance.name == name,
    ).first()
    if existing:
        raise AllianceError("nome alleanza gia in uso")

    alliance = Alliance(
        server_id=agency.server_id,
        name=name,
        treasury=0.0,
        capo_agency_id=agency.id,
    )
    db.add(alliance)
    db.flush()

    agency.alliance_id = alliance.id
    agency.alliance_role = AllianceRole.CAPO.value
    return alliance


def join_alliance(db: Session, agency: Agency, alliance_id: int) -> Alliance:
    if agency.alliance_id:
        raise AllianceError("sei gia in un'alleanza")
    alliance = db.get(Alliance, alliance_id)
    if not alliance or alliance.server_id != agency.server_id:
        raise AllianceError("alleanza non trovata")
    members = db.query(Agency).filter(Agency.alliance_id == alliance_id).count()
    if members >= B.ALLIANCE_MAX_MEMBERS:
        raise AllianceError(f"alleanza al completo ({B.ALLIANCE_MAX_MEMBERS} membri)")
    agency.alliance_id = alliance_id
    agency.alliance_role = AllianceRole.MEMBRO.value
    return alliance


def leave_alliance(db: Session, agency: Agency) -> None:
    if not agency.alliance_id:
        raise AllianceError("non sei in un'alleanza")
    alliance = db.get(Alliance, agency.alliance_id)
    if not alliance:
        agency.alliance_id = None
        agency.alliance_role = None
        return

    if alliance.capo_agency_id == agency.id:
        other = db.query(Agency).filter(
            Agency.alliance_id == alliance.id,
            Agency.id != agency.id,
        ).first()
        if other:
            alliance.capo_agency_id = other.id
            other.alliance_role = AllianceRole.CAPO.value
        else:
            db.delete(alliance)
            agency.alliance_id = None
            agency.alliance_role = None
            return

    agency.alliance_id = None
    agency.alliance_role = None


def deposit_treasury(db: Session, agency: Agency, amount: float) -> Alliance:
    if not agency.alliance_id:
        raise AllianceError("non sei in un'alleanza")
    if amount <= 0:
        raise AllianceError("importo non valido")
    if agency.balance < amount:
        raise AllianceError("saldo insufficiente")
    alliance = db.get(Alliance, agency.alliance_id)
    agency.balance -= amount
    alliance.treasury += amount
    return alliance


def withdraw_treasury(db: Session, agency: Agency, amount: float) -> Alliance:
    if not agency.alliance_id:
        raise AllianceError("non sei in un'alleanza")
    if agency.alliance_role not in (AllianceRole.CAPO.value, AllianceRole.COLONNELLO.value):
        raise AllianceError("solo capo e colonnelli possono prelevare")
    if amount <= 0:
        raise AllianceError("importo non valido")
    alliance = db.get(Alliance, agency.alliance_id)
    if alliance.treasury < amount:
        raise AllianceError("tesoreria insufficiente")
    alliance.treasury -= amount
    agency.balance += amount
    return alliance


def promote_colonnello(db: Session, agency: Agency, target_id: int) -> Agency:
    if agency.alliance_role != AllianceRole.CAPO.value:
        raise AllianceError("solo il capo puo promuovere colonnelli")
    target = db.get(Agency, target_id)
    if not target or target.alliance_id != agency.alliance_id:
        raise AllianceError("agenzia non nell'alleanza")
    colonnelli = db.query(Agency).filter(
        Agency.alliance_id == agency.alliance_id,
        Agency.alliance_role == AllianceRole.COLONNELLO.value,
    ).count()
    if colonnelli >= B.ALLIANCE_MAX_COLONNELLI:
        raise AllianceError(f"massimo {B.ALLIANCE_MAX_COLONNELLI} colonnelli")
    target.alliance_role = AllianceRole.COLONNELLO.value
    return target


def transfer_mission_to_alliance(db: Session, agency: Agency, mission_id: int):
    """§12 — trasferisce una missione Verde al pool comune dell'alleanza."""
    from app.models.core import Mission
    from app.gamedata.enums import AlarmLevel, MissionStatus

    if not agency.alliance_id:
        raise AllianceError("non sei in un'alleanza")

    mission = db.get(Mission, mission_id)
    if not mission or mission.agency_id != agency.id:
        raise AllianceError("missione non trovata o non tua")
    if mission.status != MissionStatus.ASSIGNED.value:
        raise AllianceError("solo missioni non ancora lanciate possono essere trasferite")
    if mission.alarm != AlarmLevel.VERDE.value:
        raise AllianceError("solo missioni in allarme Verde possono essere trasferite")

    mission.transferred_from_agency_id = agency.id
    mission.agency_id = None
    mission.alliance_id = agency.alliance_id
    return mission
