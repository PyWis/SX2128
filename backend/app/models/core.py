"""Modelli SQLAlchemy — entita principali (Sviluppo.md §3)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    agencies: Mapped[list["Agency"]] = relationship(back_populates="user")


class Server(Base):
    """Shard di gioco — fino a 256 agenzie (Piano Tanaka)."""
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    server_type: Mapped[str] = mapped_column(String(20), default="f2p")  # ServerType
    speed: Mapped[int] = mapped_column(Integer, default=1)               # 1 standard, 4 campioni
    capacity: Mapped[int] = mapped_column(Integer, default=256)
    current_day: Mapped[int] = mapped_column(Integer, default=0)         # giorno di gioco (t)
    cycle: Mapped[int] = mapped_column(Integer, default=1)               # ciclo da 40 giorni
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished: Mapped[bool] = mapped_column(Boolean, default=False)

    agencies: Mapped[list["Agency"]] = relationship(back_populates="server")


class Agency(Base):
    """L'Agenzia di Difesa del giocatore."""
    __tablename__ = "agencies"
    __table_args__ = (UniqueConstraint("user_id", "server_id", name="uq_user_server"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"))
    name: Mapped[str] = mapped_column(String(120))

    # §1 Governo
    culture: Mapped[str] = mapped_column(String(40))                    # CultureId
    loyalty_days: Mapped[int] = mapped_column(Integer, default=0)       # giorni di fedelta
    base_lat: Mapped[float] = mapped_column(Float, default=0.0)
    base_lon: Mapped[float] = mapped_column(Float, default=0.0)

    # §2 Bilancio
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    in_default: Mapped[bool] = mapped_column(Boolean, default=False)

    # Edifici (§4, §5, §7)
    barracks_capacity: Mapped[int] = mapped_column(Integer, default=10)
    hospital_capacity: Mapped[int] = mapped_column(Integer, default=2)
    hangar_slots: Mapped[int] = mapped_column(Integer, default=3)

    # ESPO e classifica (§9.1, §11)
    espo_today: Mapped[float] = mapped_column(Float, default=0.0)        # pool del giorno
    espo_total: Mapped[float] = mapped_column(Float, default=0.0)        # lifetime (spareggio)
    missions_completed: Mapped[int] = mapped_column(Integer, default=0)  # punteggio

    # Stato attivita (§9.1)
    last_login: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    cut_by_ug: Mapped[bool] = mapped_column(Boolean, default=False)

    # Onboarding (§0.2)
    ug_grace_active: Mapped[bool] = mapped_column(Boolean, default=True)
    first_mission_done: Mapped[bool] = mapped_column(Boolean, default=False)
    recruited_today: Mapped[bool] = mapped_column(Boolean, default=False)

    alliance_id: Mapped[int | None] = mapped_column(ForeignKey("alliances.id"), nullable=True)
    alliance_role: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # §6 F6 — pool di riserva premium (acquisti shop anti-P2W)
    premium_pool_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped["User"] = relationship(back_populates="agencies")
    server: Mapped["Server"] = relationship(back_populates="agencies")
    pilots: Mapped[list["Pilot"]] = relationship(back_populates="agency", cascade="all, delete-orphan")
    fighters: Mapped[list["Fighter"]] = relationship(back_populates="agency", cascade="all, delete-orphan")
    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="agency", cascade="all, delete-orphan")
    loans: Mapped[list["Loan"]] = relationship(back_populates="agency", cascade="all, delete-orphan")
    alliance: Mapped["Alliance | None"] = relationship(back_populates="members", foreign_keys=[alliance_id])


class Pilot(Base):
    """§3.2, §4.2-4.3."""
    __tablename__ = "pilots"

    id: Mapped[int] = mapped_column(primary_key=True)
    agency_id: Mapped[int] = mapped_column(ForeignKey("agencies.id"))
    name: Mapped[str] = mapped_column(String(120))
    origin_culture: Mapped[str] = mapped_column(String(40))

    espo_pct: Mapped[float] = mapped_column(Float, default=0.0)
    str_pct: Mapped[float] = mapped_column(Float, default=0.0)
    strs_pct: Mapped[float] = mapped_column(Float, default=0.0)

    # licenze possedute: {"A": "silver", "B": "bronze", ...}
    licenses: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="barracks")   # UnitStatus
    training_until_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # §4.2/§4.3: tipo addestramento in corso ("stat:espo"/"stat:str"/"stat:strs" o "lic:A:bronze")
    training_info: Mapped[str | None] = mapped_column(String(40), nullable=True)

    agency: Mapped["Agency"] = relationship(back_populates="pilots")


class Fighter(Base):
    """§3.3, §4.4-4.5."""
    __tablename__ = "fighters"

    id: Mapped[int] = mapped_column(primary_key=True)
    agency_id: Mapped[int] = mapped_column(ForeignKey("agencies.id"))
    name: Mapped[str] = mapped_column(String(120))
    origin_culture: Mapped[str] = mapped_column(String(40))

    vit: Mapped[int] = mapped_column(Integer, default=100)
    strg: Mapped[int] = mapped_column("str", Integer, default=50)
    dif: Mapped[int] = mapped_column(Integer, default=50)
    mov: Mapped[int] = mapped_column(Integer, default=10)
    spa: Mapped[int] = mapped_column(Integer, default=0)

    # §6.1 Equipaggiamento: chiave livello (es. "bronze1") o None = non equipaggiato
    weapon_key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    armor_terra_key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    armor_spazio_key: Mapped[str | None] = mapped_column(String(20), nullable=True)

    missions_completed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="barracks")   # UnitStatus

    # §4.4 Addestramento stat: giorno di completamento e stat in corso
    training_until_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    training_stat: Mapped[str | None] = mapped_column(String(10), nullable=True)

    agency: Mapped["Agency"] = relationship(back_populates="fighters")

    @property
    def tabi(self) -> int:
        return self.strg + self.dif + self.mov + self.spa


class Vehicle(Base):
    """§8 — istanza di un blueprint."""
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    agency_id: Mapped[int] = mapped_column(ForeignKey("agencies.id"))
    project: Mapped[str] = mapped_column(String(60))           # chiave blueprint
    vclass: Mapped[str] = mapped_column(String(30))            # VehicleClass
    pilot_id: Mapped[int | None] = mapped_column(ForeignKey("pilots.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="barracks")  # hangar/in_flight/eliminated
    return_day: Mapped[float | None] = mapped_column(Float, nullable=True)  # ETA in giorni di gioco

    # §6.2 Missili (si azzerano al rientro; max 4 totali per vettore)
    missiles_terra_key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    missiles_terra_count: Mapped[int] = mapped_column(Integer, default=0)
    missiles_spazio_key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    missiles_spazio_count: Mapped[int] = mapped_column(Integer, default=0)

    agency: Mapped["Agency"] = relationship(back_populates="vehicles")


class Loan(Base):
    """§2.2-2.3."""
    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(primary_key=True)
    agency_id: Mapped[int] = mapped_column(ForeignKey("agencies.id"))
    loan_type: Mapped[str] = mapped_column(String(20))        # LoanType
    principal: Mapped[float] = mapped_column(Float)
    rate_amount: Mapped[float] = mapped_column(Float)         # rata giornaliera
    rates_left: Mapped[int] = mapped_column(Integer)

    agency: Mapped["Agency"] = relationship(back_populates="loans")


class Mission(Base):
    """§9."""
    __tablename__ = "missions"

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"))
    agency_id: Mapped[int | None] = mapped_column(ForeignKey("agencies.id"), nullable=True)
    mission_type: Mapped[str] = mapped_column(String(30))     # MissionType
    alarm: Mapped[str] = mapped_column(String(10), default="verde")  # AlarmLevel
    status: Mapped[str] = mapped_column(String(20), default="assigned")

    target_lat: Mapped[float] = mapped_column(Float, default=0.0)
    target_lon: Mapped[float] = mapped_column(Float, default=0.0)
    pn: Mapped[float] = mapped_column(Float, default=0.0)     # potenza nemico
    reward_estimate: Mapped[float] = mapped_column(Float, default=0.0)

    assigned_day: Mapped[int] = mapped_column(Integer, default=0)
    deadline_day: Mapped[int] = mapped_column(Integer, default=0)
    visible_at_hour: Mapped[int] = mapped_column(Integer, default=0)  # ora casuale 0-23

    # §9.10 F3 — sortie: dati di lancio e risoluzione
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    fighters_json: Mapped[list | None] = mapped_column(JSON, nullable=True)   # lista ID combattenti
    sortie_return_day: Mapped[float | None] = mapped_column(Float, nullable=True)  # ETA
    resolution_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # log combattimento

    # §9.11 F4 — sortie multi-missione (catena di tappe)
    chain_leg: Mapped[int] = mapped_column(Integer, default=0)  # 0 = solo o prima tappa

    # §9.9 F4 — evacuazione civili
    civili_da_salvare: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # §12 F5 — pool missioni alleanza e split ricompensa trasferimento
    alliance_id: Mapped[int | None] = mapped_column(ForeignKey("alliances.id"), nullable=True)
    transferred_from_agency_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ShopTransaction(Base):
    """§6 F6 — transazione shop (acquisto pacchetti, ticket)."""
    __tablename__ = "shop_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    agency_id: Mapped[int | None] = mapped_column(ForeignKey("agencies.id"), nullable=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"))
    package_key: Mapped[str] = mapped_column(String(60))
    price_eur: Mapped[float] = mapped_column(Float)
    agenda_2030_eur: Mapped[float] = mapped_column(Float)
    cycle_at_purchase: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Alliance(Base):
    """§12."""
    __tablename__ = "alliances"

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"))
    name: Mapped[str] = mapped_column(String(120))
    treasury: Mapped[float] = mapped_column(Float, default=0.0)
    capo_agency_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    members: Mapped[list["Agency"]] = relationship(
        back_populates="alliance", foreign_keys="Agency.alliance_id"
    )


class ChatMessage(Base):
    """§13."""
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"))
    channel_type: Mapped[str] = mapped_column(String(20))     # ChatChannelType
    channel_key: Mapped[str] = mapped_column(String(80), default="")  # cultura id / alleanza id / dm pair
    author_agency_id: Mapped[int | None] = mapped_column(ForeignKey("agencies.id"), nullable=True)
    body: Mapped[str] = mapped_column(String(4000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
