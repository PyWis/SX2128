"""Schemi Pydantic per l'API."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.gamedata.enums import CultureId, ServerType


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ServerCreate(BaseModel):
    name: str
    server_type: ServerType = ServerType.F2P


class AgencyCreate(BaseModel):
    server_id: int
    name: str
    culture: CultureId
    base_lat: float = 0.0
    base_lon: float = 0.0


class RecruitRequest(BaseModel):
    option: str


class AgencyOut(BaseModel):
    id: int
    name: str
    culture: str
    loyalty_days: int
    balance: float
    in_default: bool
    barracks_capacity: int
    hospital_capacity: int
    hangar_slots: int
    espo_today: float
    espo_total: float
    missions_completed: int

    class Config:
        from_attributes = True
