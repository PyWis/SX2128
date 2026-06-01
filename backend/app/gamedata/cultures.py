"""Tabella Culture — GDD §1.1.

Il moltiplicatore di fedelta e LINEARE con reset a 0 al cambio cultura (§1, §14):
    contributo = base * (1 + fedelta_pct/100 * giorni_fedelta)

I `perk` sono identificatori macchina dei vantaggi unici; la loro applicazione
e gestita nei rispettivi servizi (economia, missioni, licenze, hangar...).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .enums import CultureId


@dataclass(frozen=True)
class Culture:
    id: CultureId
    nome: str
    emoji: str
    base_r_giorno: int        # contributo base R/giorno
    fedelta_pct_giorno: float # incremento lineare %/giorno
    vantaggio: str            # descrizione leggibile (§1.1)
    perks: set[str] = field(default_factory=set)
    # distribuzione onomastica (§3.4): mappa locale -> peso
    nomi: dict[str, int] = field(default_factory=dict)


CULTURES: dict[CultureId, Culture] = {
    CultureId.NORDAMERICANA: Culture(
        id=CultureId.NORDAMERICANA, nome="Nordamericana", emoji="\U0001F310",
        base_r_giorno=500, fedelta_pct_giorno=2.0,
        vantaggio="Missioni +25% · Aerei -10% (1/g)",
        perks={"mission_reward_+25", "aircraft_discount_10_once_day"},
        nomi={"inglese": 60, "francese": 10, "spagnolo": 30},
    ),
    CultureId.EUROPEA: Culture(
        id=CultureId.EUROPEA, nome="Europea", emoji="\U0001F3DB",
        base_r_giorno=250, fedelta_pct_giorno=3.0,
        vantaggio="Tempo licenze -25%",
        perks={"license_time_-25"},
        nomi={"francese": 20, "italiano": 20, "polacco": 10, "olandese": 10,
              "spagnolo": 20, "tedesco": 20},
    ),
    CultureId.CINESE: Culture(
        id=CultureId.CINESE, nome="Cinese", emoji="\U0001F409",
        base_r_giorno=150, fedelta_pct_giorno=3.5,
        vantaggio="Hangar +2 slot permanenti",
        perks={"hangar_+2"},
        nomi={"cinese": 100},
    ),
    CultureId.AFRICANA: Culture(
        id=CultureId.AFRICANA, nome="Africana", emoji="\U0001F30D",
        base_r_giorno=100, fedelta_pct_giorno=1.5,
        vantaggio="+50 R/g per ogni ufficiale",
        perks={"income_+50_per_officer"},
        nomi={"arabo": 20, "swahili": 40, "yoruba": 20, "amarico": 20},
    ),
    CultureId.INDIANA: Culture(
        id=CultureId.INDIANA, nome="Indiana", emoji="\U0001F54C",
        base_r_giorno=450, fedelta_pct_giorno=2.0,
        vantaggio="1 recluta gratis/g · +2 postazioni missione",
        perks={"free_recruit_per_day", "mission_slots_+2"},
        nomi={"indo_pakistano": 70, "iraniano": 20, "russo": 10},
    ),
    CultureId.PACIFICA: Culture(
        id=CultureId.PACIFICA, nome="Pacifica", emoji="\U0001F30F",
        base_r_giorno=600, fedelta_pct_giorno=1.0,
        vantaggio="Manutenzione aerea gratis",
        perks={"free_air_maintenance"},
        nomi={"giapponese": 30, "coreano": 20, "malese": 20, "filippino": 20, "inglese": 10},
    ),
    CultureId.LATINOAMERICANA: Culture(
        id=CultureId.LATINOAMERICANA, nome="Latinoamericana", emoji="\U0001F33A",
        base_r_giorno=100, fedelta_pct_giorno=1.0,
        vantaggio="ESPO ×4",
        perks={"espo_x4"},
        nomi={"spagnolo": 80, "portoghese": 20},
    ),
    CultureId.LUNARE: Culture(
        id=CultureId.LUNARE, nome="Lunare", emoji="\U0001F319",
        base_r_giorno=1000, fedelta_pct_giorno=0.5,
        vantaggio="-20% spazioplani · +4 postazioni · Licenza D-Bronze nativa",
        perks={"spaceplane_discount_20", "mission_slots_+4", "native_d_bronze"},
        nomi={"inglese": 30, "europeo": 20, "russo": 40, "giapponese": 10},
    ),
    CultureId.CYBER: Culture(
        id=CultureId.CYBER, nome="Cyber", emoji="\U0001F4BB",
        base_r_giorno=250, fedelta_pct_giorno=2.0,
        vantaggio="ESPO ×2",
        perks={"espo_x2"},
        nomi={"nickname": 100},
    ),
    CultureId.NON_TECNOLOGICA: Culture(
        id=CultureId.NON_TECNOLOGICA, nome="Non Tecnologica", emoji="\U0001F33F",
        base_r_giorno=50, fedelta_pct_giorno=5.0,
        vantaggio="STR combattenti nativi +30%",
        perks={"native_str_+30"},
        nomi={"mitologico": 100},
    ),
}


def get_culture(culture_id: CultureId | str) -> Culture:
    if isinstance(culture_id, str):
        culture_id = CultureId(culture_id)
    return CULTURES[culture_id]
