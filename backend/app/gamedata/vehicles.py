"""Catalogo Vettori — GDD §8.1-8.6.

Ogni progetto e un blueprint statico. Le licenze richieste sono espresse come
lista di coppie (tipo, tier minimo). La velocita e in M (aerei) o DXC (spazio);
il trasferimento Terra-Luna in giorni (spazioplani da missione).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .enums import LicenseTier, LicenseType, VehicleClass

Req = tuple[LicenseType, LicenseTier]


@dataclass(frozen=True)
class VehicleBlueprint:
    project: str
    vclass: VehicleClass
    cost: int
    maintenance: int                 # R/giorno
    licenses: tuple[Req, ...]
    # campi specifici per classe (0/None se non pertinenti)
    espo_giorno: int = 0             # esplorazione
    attacco: int = 0                 # caccia: STR (aereo) o STRS (spazio)
    velocita: float = 0.0            # M (aereo) o DXC (spazio)
    postazioni: int = 0              # missione
    transfer_luna_giorni: float = 0.0  # spazioplani da missione
    capacita_h: int = 0              # civili (abitanti H)


def _b(t: LicenseType, tier: LicenseTier) -> Req:
    return (t, tier)


A, B, C, D, E = LicenseType.A, LicenseType.B, LicenseType.C, LicenseType.D, LicenseType.E
BR, SI, GO, PL = LicenseTier.BRONZE, LicenseTier.SILVER, LicenseTier.GOLD, LicenseTier.PLATINUM


# §8.1 Aeroplani da Esplorazione (licenza A)
EXPLORATION = [
    VehicleBlueprint("Dubai", VehicleClass.EXPLORATION, 100, 5, (_b(A, BR),), espo_giorno=100),
    VehicleBlueprint("Tokyo", VehicleClass.EXPLORATION, 150, 2, (_b(A, BR),), espo_giorno=100),
    VehicleBlueprint("Seoul", VehicleClass.EXPLORATION, 200, 1, (_b(A, BR),), espo_giorno=120),
    VehicleBlueprint("Seattle", VehicleClass.EXPLORATION, 400, 20, (_b(A, SI),), espo_giorno=200),
    VehicleBlueprint("San Paolo", VehicleClass.EXPLORATION, 600, 10, (_b(A, SI),), espo_giorno=200),
    VehicleBlueprint("Buenos Aires", VehicleClass.EXPLORATION, 800, 20, (_b(A, SI),), espo_giorno=250),
    VehicleBlueprint("Shenzhen", VehicleClass.EXPLORATION, 1500, 50, (_b(A, GO),), espo_giorno=400),
    VehicleBlueprint("San Pietroburgo", VehicleClass.EXPLORATION, 2000, 25, (_b(A, GO),), espo_giorno=400),
    VehicleBlueprint("Roma", VehicleClass.EXPLORATION, 2500, 50, (_b(A, GO),), espo_giorno=500),
    VehicleBlueprint("New York", VehicleClass.EXPLORATION, 4000, 200, (_b(A, PL),), espo_giorno=1000),
]

# §8.2 Aeroplani da Caccia (licenza B) — attacco in STR, velocita in M
FIGHTER = [
    VehicleBlueprint("Tikal", VehicleClass.FIGHTER, 200, 10, (_b(B, BR),), attacco=100, velocita=1.5),
    VehicleBlueprint("Petra", VehicleClass.FIGHTER, 400, 10, (_b(B, BR),), attacco=150, velocita=1.3),
    VehicleBlueprint("Chan Chan", VehicleClass.FIGHTER, 800, 10, (_b(B, BR),), attacco=200, velocita=1.1),
    VehicleBlueprint("Kyoto", VehicleClass.FIGHTER, 1000, 50, (_b(B, SI),), attacco=400, velocita=1.8),
    VehicleBlueprint("Angkor", VehicleClass.FIGHTER, 2000, 50, (_b(B, SI),), attacco=500, velocita=1.6),
    VehicleBlueprint("Pompei", VehicleClass.FIGHTER, 4000, 100, (_b(B, SI),), attacco=700, velocita=1.4),
    VehicleBlueprint("Tebe", VehicleClass.FIGHTER, 5000, 200, (_b(B, GO),), attacco=800, velocita=2.4),
    VehicleBlueprint("Ile-Ife", VehicleClass.FIGHTER, 10000, 200, (_b(B, GO),), attacco=1000, velocita=2.6),
    VehicleBlueprint("Site Eleven", VehicleClass.FIGHTER, 12000, 300, (_b(B, GO),), attacco=1200, velocita=2.5),
    VehicleBlueprint("Xi'an", VehicleClass.FIGHTER, 50000, 500, (_b(B, PL),), attacco=1500, velocita=3.0),
]

# §8.3 Aeroplani da Missione (licenze A/B + C)
MISSION = [
    VehicleBlueprint("Belisario", VehicleClass.MISSION, 400, 20, (_b(A, SI), _b(B, SI), _b(C, BR)), postazioni=8, velocita=0.7),
    VehicleBlueprint("Garibaldi", VehicleClass.MISSION, 600, 20, (_b(A, SI), _b(B, SI), _b(C, BR)), postazioni=8, velocita=0.8),
    VehicleBlueprint("Rommel", VehicleClass.MISSION, 800, 20, (_b(A, SI), _b(B, SI), _b(C, BR)), postazioni=8, velocita=0.9),
    VehicleBlueprint("Epaminonda", VehicleClass.MISSION, 1000, 30, (_b(A, SI), _b(B, SI), _b(C, SI)), postazioni=12, velocita=0.8),
    VehicleBlueprint("al-Walid", VehicleClass.MISSION, 1200, 30, (_b(A, GO), _b(B, GO), _b(C, SI)), postazioni=12, velocita=0.9),
    VehicleBlueprint("Giulio Cesare", VehicleClass.MISSION, 1500, 30, (_b(A, GO), _b(B, GO), _b(C, SI)), postazioni=12, velocita=1.0),
    VehicleBlueprint("Subutai", VehicleClass.MISSION, 1800, 40, (_b(A, GO), _b(B, GO), _b(C, GO)), postazioni=16, velocita=0.8),
    VehicleBlueprint("Napoleone", VehicleClass.MISSION, 2000, 40, (_b(A, GO), _b(B, GO), _b(C, GO)), postazioni=16, velocita=1.0),
    VehicleBlueprint("Annibale", VehicleClass.MISSION, 2500, 40, (_b(A, PL), _b(B, PL), _b(C, GO)), postazioni=16, velocita=1.2),
    VehicleBlueprint("Alessandro", VehicleClass.MISSION, 5000, 50, (_b(A, PL), _b(B, PL), _b(C, PL)), postazioni=20, velocita=1.5),
]

# §8.4 Spazioplani da Caccia (licenze B + D) — attacco in STRS, velocita in DXC
SPACE_FIGHTER = [
    VehicleBlueprint("Cygnus", VehicleClass.SPACE_FIGHTER, 2000, 100, (_b(B, SI), _b(D, BR)), attacco=100, velocita=1.5),
    VehicleBlueprint("Crux", VehicleClass.SPACE_FIGHTER, 4000, 100, (_b(B, SI), _b(D, BR)), attacco=150, velocita=1.3),
    VehicleBlueprint("Canis", VehicleClass.SPACE_FIGHTER, 8000, 100, (_b(B, GO), _b(D, BR)), attacco=200, velocita=1.1),
    VehicleBlueprint("Gemini", VehicleClass.SPACE_FIGHTER, 10000, 500, (_b(B, GO), _b(D, BR)), attacco=400, velocita=1.8),
    VehicleBlueprint("Cassiopeia", VehicleClass.SPACE_FIGHTER, 20000, 500, (_b(B, GO), _b(D, SI)), attacco=500, velocita=1.6),
    VehicleBlueprint("Scorpius", VehicleClass.SPACE_FIGHTER, 40000, 1000, (_b(B, GO), _b(D, SI)), attacco=700, velocita=1.4),
    VehicleBlueprint("Taurus", VehicleClass.SPACE_FIGHTER, 50000, 2000, (_b(B, PL), _b(D, SI)), attacco=800, velocita=2.4),
    VehicleBlueprint("Leo", VehicleClass.SPACE_FIGHTER, 100000, 2000, (_b(B, PL), _b(D, SI)), attacco=1000, velocita=2.6),
    VehicleBlueprint("Orion", VehicleClass.SPACE_FIGHTER, 120000, 3000, (_b(B, PL), _b(D, GO)), attacco=1200, velocita=2.5),
    VehicleBlueprint("Ursa", VehicleClass.SPACE_FIGHTER, 500000, 5000, (_b(B, PL), _b(D, GO)), attacco=1500, velocita=3.0),
]

# §8.5 Spazioplani da Missione (licenze C + D)
SPACE_MISSION = [
    VehicleBlueprint("Antares", VehicleClass.SPACE_MISSION, 400, 20, (_b(C, SI), _b(D, SI)), postazioni=8, transfer_luna_giorni=4.0),
    VehicleBlueprint("Acrux", VehicleClass.SPACE_MISSION, 600, 20, (_b(C, SI), _b(D, SI)), postazioni=8, transfer_luna_giorni=3.5),
    VehicleBlueprint("Altair", VehicleClass.SPACE_MISSION, 800, 20, (_b(C, GO), _b(D, SI)), postazioni=8, transfer_luna_giorni=3.0),
    VehicleBlueprint("Hadar", VehicleClass.SPACE_MISSION, 1000, 30, (_b(C, GO), _b(D, SI)), postazioni=12, transfer_luna_giorni=4.0),
    VehicleBlueprint("Betelgeuse", VehicleClass.SPACE_MISSION, 1200, 30, (_b(C, GO), _b(D, GO)), postazioni=12, transfer_luna_giorni=3.5),
    VehicleBlueprint("Rigel", VehicleClass.SPACE_MISSION, 1500, 30, (_b(C, GO), _b(D, GO)), postazioni=12, transfer_luna_giorni=3.0),
    VehicleBlueprint("Vega", VehicleClass.SPACE_MISSION, 1800, 40, (_b(C, PL), _b(D, GO)), postazioni=16, transfer_luna_giorni=3.5),
    VehicleBlueprint("Rigil", VehicleClass.SPACE_MISSION, 2000, 40, (_b(C, PL), _b(D, GO)), postazioni=16, transfer_luna_giorni=3.0),
    VehicleBlueprint("Canopo", VehicleClass.SPACE_MISSION, 2500, 40, (_b(C, PL), _b(D, PL)), postazioni=16, transfer_luna_giorni=2.5),
    VehicleBlueprint("Sirio", VehicleClass.SPACE_MISSION, 5000, 50, (_b(C, PL), _b(D, PL)), postazioni=20, transfer_luna_giorni=2.0),
]

# §8.6 Spazioplani Civili (licenze D + E) — capacita in H
CIVILIAN = [
    VehicleBlueprint("Americo", VehicleClass.CIVILIAN, 500000, 10000, (_b(D, GO), _b(E, BR)), capacita_h=10000),
    VehicleBlueprint("Cristoforo", VehicleClass.CIVILIAN, 1000000, 10000, (_b(D, GO), _b(E, SI)), capacita_h=20000),
    VehicleBlueprint("Neil", VehicleClass.CIVILIAN, 2000000, 10000, (_b(D, PL), _b(E, GO)), capacita_h=50000),
]


ALL_VEHICLES: list[VehicleBlueprint] = (
    EXPLORATION + FIGHTER + MISSION + SPACE_FIGHTER + SPACE_MISSION + CIVILIAN
)
VEHICLES_BY_PROJECT: dict[str, VehicleBlueprint] = {v.project: v for v in ALL_VEHICLES}


def get_vehicle(project: str) -> VehicleBlueprint:
    return VEHICLES_BY_PROJECT[project]
