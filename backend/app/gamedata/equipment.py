"""Equipaggiamento Combattenti e Missili — GDD §6.

§6.1 Equipaggiamento: armi (+STR) e armature terrestre/spaziale (+DIF, -MOV o -SPA).
     Al rientro da una missione il 30% dell'equipaggiamento si consuma (§6).
§6.2 Missili: fino a 4 per vettore da caccia; si azzerano al rientro.
"""
from __future__ import annotations

from dataclasses import dataclass

EQUIP_CONSUMPTION_RATE = 0.30  # §6 consumo al rientro
MAX_MISSILES_PER_VEHICLE = 4   # §6.2 / pool unico per sortie (§9.11)


@dataclass(frozen=True)
class EquipmentLevel:
    livello: str
    cost: int
    # arma
    arma_str: int
    arma_mov: int
    # armatura terrestre
    terra_dif: int
    terra_mov: int
    # armatura spaziale
    spazio_dif: int
    spazio_spa: int


# §6.1 — i tre slot (arma / armatura terrestre / armatura spaziale) condividono livello e costo
EQUIPMENT: dict[str, EquipmentLevel] = {
    "bronze1": EquipmentLevel("Bronze 1", 100, arma_str=10, arma_mov=0, terra_dif=10, terra_mov=-1, spazio_dif=10, spazio_spa=-3),
    "bronze2": EquipmentLevel("Bronze 2", 150, arma_str=12, arma_mov=0, terra_dif=15, terra_mov=-3, spazio_dif=15, spazio_spa=-10),
    "bronze3": EquipmentLevel("Bronze 3", 200, arma_str=20, arma_mov=-5, terra_dif=20, terra_mov=-10, spazio_dif=20, spazio_spa=-30),
    "silver1": EquipmentLevel("Silver 1", 500, arma_str=20, arma_mov=0, terra_dif=25, terra_mov=-1, spazio_dif=25, spazio_spa=0),
    "silver2": EquipmentLevel("Silver 2", 750, arma_str=25, arma_mov=-3, terra_dif=30, terra_mov=-3, spazio_dif=30, spazio_spa=-5),
    "silver3": EquipmentLevel("Silver 3", 1000, arma_str=30, arma_mov=-8, terra_dif=40, terra_mov=-10, spazio_dif=40, spazio_spa=-20),
    "gold1": EquipmentLevel("Gold 1", 2000, arma_str=40, arma_mov=0, terra_dif=50, terra_mov=-2, spazio_dif=50, spazio_spa=5),
    "gold2": EquipmentLevel("Gold 2", 2500, arma_str=50, arma_mov=-4, terra_dif=60, terra_mov=-5, spazio_dif=60, spazio_spa=0),
    "gold3": EquipmentLevel("Gold 3", 3000, arma_str=60, arma_mov=-10, terra_dif=75, terra_mov=-15, spazio_dif=75, spazio_spa=-10),
}


@dataclass(frozen=True)
class MissileLevel:
    livello: str
    cost_terra: int
    str_terra: int     # +STR (intercettazione terrestre)
    cost_spazio: int
    strs_spazio: int   # +STRS (intercettazione lunare)


# §6.2
MISSILES: dict[str, MissileLevel] = {
    "bronze": MissileLevel("Bronze", cost_terra=10, str_terra=50, cost_spazio=100, strs_spazio=50),
    "silver": MissileLevel("Silver", cost_terra=100, str_terra=250, cost_spazio=1000, strs_spazio=250),
    "gold": MissileLevel("Gold", cost_terra=500, str_terra=500, cost_spazio=5000, strs_spazio=500),
    "platinum": MissileLevel("Platinum", cost_terra=2000, str_terra=1000, cost_spazio=20000, strs_spazio=1000),
}
