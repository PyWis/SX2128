"""Edifici, licenze, prestiti e parametri economici — GDD §2, §4, §5, §7, §10."""
from __future__ import annotations

from dataclasses import dataclass

from .enums import LicenseTier, LicenseType, LoanType

# --- Stato iniziale (§0.2) ---
STARTING_CAPITAL = 2000
STARTING_BARRACKS = 10
STARTING_HOSPITAL = 2
STARTING_HANGAR = 3
UG_GRACE_MAX_DAYS = 7  # §0.2 cap di sicurezza grazia UG


# --- §4.1 Caserma: upgrade capacita (costo R per posto, fino a soglia) ---
# lista ordinata di (soglia_max, costo_per_posto)
BARRACKS_UPGRADES = [(20, 1000), (30, 2000), (40, 3000), (50, 5000), (80, 10000), (100, 20000)]
BARRACKS_MAX = 100

# --- §5.1 Ospedale ---
HOSPITAL_UPGRADES = [(3, 1000), (5, 2000), (10, 3000), (15, 5000), (25, 10000)]
HOSPITAL_MAX = 25

# --- §7 Hangar: (slot, costo, requisito) ---
@dataclass(frozen=True)
class HangarSlot:
    slot: int
    cost: int
    requisito: str | None


HANGAR_SLOTS = [
    HangarSlot(3, 0, "1 aereo esplorazione + 1 aereo missione"),  # base gratis
    HangarSlot(4, 2000, None),
    HangarSlot(5, 4000, None),
    HangarSlot(6, 10000, "Almeno 1 aereo da caccia"),
    HangarSlot(7, 20000, None),
    HangarSlot(8, 50000, None),
    HangarSlot(9, 100000, "Almeno 1 aereo spaziale"),
    HangarSlot(10, 200000, None),
    HangarSlot(11, 500000, None),
    HangarSlot(12, 1000000, "Almeno 1 aereo da trasporto civile"),
]
HANGAR_MAX = 12


# --- §4.2 Licenze pilota: costo (R) e durata (giorni) per tipo x tier ---
@dataclass(frozen=True)
class LicenseSpec:
    cost: int
    giorni: int


# None = non disponibile (E-Platinum)
LICENSES: dict[LicenseType, dict[LicenseTier, LicenseSpec | None]] = {
    LicenseType.A: {
        LicenseTier.BRONZE: LicenseSpec(1000, 1), LicenseTier.SILVER: LicenseSpec(5000, 5),
        LicenseTier.GOLD: LicenseSpec(25000, 12), LicenseTier.PLATINUM: LicenseSpec(100000, 30),
    },
    LicenseType.B: {
        LicenseTier.BRONZE: LicenseSpec(2500, 2), LicenseTier.SILVER: LicenseSpec(10000, 7),
        LicenseTier.GOLD: LicenseSpec(40000, 15), LicenseTier.PLATINUM: LicenseSpec(200000, 30),
    },
    LicenseType.C: {
        LicenseTier.BRONZE: LicenseSpec(1000, 1), LicenseTier.SILVER: LicenseSpec(5000, 3),
        LicenseTier.GOLD: LicenseSpec(10000, 5), LicenseTier.PLATINUM: LicenseSpec(25000, 7),
    },
    LicenseType.D: {
        LicenseTier.BRONZE: LicenseSpec(2500, 2), LicenseTier.SILVER: LicenseSpec(10000, 7),
        LicenseTier.GOLD: LicenseSpec(50000, 15), LicenseTier.PLATINUM: LicenseSpec(200000, 30),
    },
    LicenseType.E: {
        LicenseTier.BRONZE: LicenseSpec(10000, 1), LicenseTier.SILVER: LicenseSpec(20000, 3),
        LicenseTier.GOLD: LicenseSpec(100000, 7), LicenseTier.PLATINUM: None,
    },
}


# --- §3.1 Opzioni di reclutamento: chiave -> (costo, n_piloti, n_combattenti) ---
RECRUIT_OPTIONS: dict[str, tuple[int, int, int]] = {
    "1_pilota": (100, 1, 0),
    "1_combattente": (10, 0, 1),
    "2_combattenti": (30, 0, 2),
    "3_combattenti": (80, 0, 3),
    "4_combattenti": (200, 0, 4),
    "pilota_2_combattenti": (200, 1, 2),
    "pilota_4_combattenti": (500, 1, 4),
}


# --- Addestramento (§4.3, §4.4) ---
PILOT_TRAIN_COST = 1000     # R/sessione, +1% a una stat
PILOT_TRAIN_CAP = 25.0      # % massimo per statistica
FIGHTER_TRAIN_COST = 250    # R/sessione, +1 punto
FIGHTER_LIMITS = {"STR": 200, "DIF": 200, "MOV": 25, "SPA": 200}
FIGHTER_VIT_REGEN = 1       # +1 VIT/g gratis in caserma
FIGHTER_VIT_MAX = 120

# --- Ospedale (§5.2) ---
HOSPITAL_HEAL_BASE = 20     # +/- 5
VIT_MAX_HEAL = 100

# --- §2.2 Prestiti: moltiplicatore contributo, rate, slot, commissione ---
@dataclass(frozen=True)
class LoanSpec:
    moltiplicatore: int   # x contributo attuale
    rate: int             # numero rate giornaliere
    slot_max: int
    commissione: float    # frazione


LOANS: dict[LoanType, LoanSpec] = {
    LoanType.CULTURA: LoanSpec(moltiplicatore=3, rate=20, slot_max=3, commissione=0.05),
    LoanType.UG: LoanSpec(moltiplicatore=10, rate=40, slot_max=2, commissione=0.20),
}

# --- §2.3 Default ---
DEFAULT_PENALTY_RATE = 0.02   # 2%/g sul credito negativo

# --- §10 Co-finanziamento UG ---
UG_COFINANCE_PER_MISSION = 100  # R x missioni completate nelle ultime 48h
