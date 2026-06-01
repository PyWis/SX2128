"""Enumerazioni di gioco condivise (GDD §1, §4, §8, §9)."""
from __future__ import annotations

import enum


class CultureId(str, enum.Enum):
    NORDAMERICANA = "nordamericana"
    EUROPEA = "europea"
    CINESE = "cinese"
    AFRICANA = "africana"
    INDIANA = "indiana"
    PACIFICA = "pacifica"
    LATINOAMERICANA = "latinoamericana"
    LUNARE = "lunare"
    CYBER = "cyber"
    NON_TECNOLOGICA = "non_tecnologica"


class LicenseType(str, enum.Enum):
    A = "A"  # Esplorazione
    B = "B"  # Combattimento
    C = "C"  # Trasporto
    D = "D"  # Spazio
    E = "E"  # Trasporto Civili


class LicenseTier(str, enum.Enum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"


class VehicleClass(str, enum.Enum):
    EXPLORATION = "exploration"        # §8.1 aeroplani da esplorazione
    FIGHTER = "fighter"                # §8.2 aeroplani da caccia
    MISSION = "mission"                # §8.3 aeroplani da missione
    SPACE_FIGHTER = "space_fighter"    # §8.4 spazioplani da caccia
    SPACE_MISSION = "space_mission"    # §8.5 spazioplani da missione
    CIVILIAN = "civilian"              # §8.6 spazioplani civili


class MissionType(str, enum.Enum):
    TERRESTRE = "terrestre"                          # §9.3 dal 1 luglio
    INTERCETTAZIONE_TERRESTRE = "intercept_terra"    # §9.3 dal 15 agosto
    INTERCETTAZIONE_LUNARE = "intercept_luna"        # §9.3 dal 1 ottobre
    LUNARE = "lunare"                                # §9.3 dal 1 novembre
    UG = "ug"                                        # §9.8 missioni speciali
    EVACUAZIONE = "evacuazione"                      # §9.9


class AlarmLevel(str, enum.Enum):
    VERDE = "verde"    # §9.2
    GIALLO = "giallo"
    ROSSO = "rosso"


class MissionStatus(str, enum.Enum):
    ASSIGNED = "assigned"      # assegnata, non ancora visibile
    AVAILABLE = "available"    # visibile e svolgibile
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    UG_RESOLVED = "ug_resolved"


class UnitStatus(str, enum.Enum):
    BARRACKS = "barracks"        # in caserma, disponibile
    HOSPITAL = "hospital"        # ferito, in cura
    IN_FLIGHT = "in_flight"      # impegnato in una sortie
    TRAINING = "training"        # in addestramento (piloti)
    ELIMINATED = "eliminated"    # morto / distrutto


class LoanType(str, enum.Enum):
    CULTURA = "cultura"
    UG = "ug"


class ServerType(str, enum.Enum):
    F2P = "f2p"
    PRO = "pro"
    CAMPIONI = "campioni"


class AllianceRole(str, enum.Enum):
    CAPO = "capo"            # Capoalleanza (§12)
    COLONNELLO = "colonnello"
    MEMBRO = "membro"


class ChatChannelType(str, enum.Enum):
    UG_NET = "ug_net"            # globale (§13)
    CULTURA = "cultura"
    ALLEANZA = "alleanza"
    DM = "dm"
    OPERAZIONE_UG = "operazione_ug"
    DELPY = "delpy"              # canale di sistema
