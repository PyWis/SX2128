"""Catalogo Shop — GDD §6 / Pianificazione Monetizzazione.

Prezzi in EUR; anti-P2W: max 1 pacchetto per ciclo di 40 giorni, max 1/giorno.
Le unità vanno nel Pool di Riserva Premium e si riscattano ai turni normali.
"""
from __future__ import annotations

from dataclasses import dataclass, field

AGENDA_2030_RATE = 0.10   # 10% del lordo devoluto ad Agenda 2030

# blueprint vettore incluso per ogni pacchetto culturale (classe missione)
_CULTURE_VEHICLE: dict[str, tuple[str, str]] = {
    "nordamericana": ("Belisario", "mission"),
    "europea":       ("Belisario", "mission"),
    "cinese":        ("Belisario", "mission"),
    "africana":      ("Belisario", "mission"),
    "indiana":       ("Belisario", "mission"),
    "pacifica":      ("Belisario", "mission"),
    "latinoamericana": ("Belisario", "mission"),
    "lunare":        ("Antares",   "space_mission"),
    "cyber":         ("Belisario", "mission"),
    "non_tecnologica": ("Belisario", "mission"),
}


@dataclass
class ShopPackage:
    key: str
    nome: str
    desc: str
    price_eur: float
    pilots: int = 0
    fighters: int = 0
    vehicle: tuple[str, str] | None = None   # (project, vclass)
    cultura: str | None = None
    package_type: str = "plus"               # "plus" | "ticket_pro" | "ticket_campioni"


def _plus(culture_id: str, nome: str) -> ShopPackage:
    veh = _CULTURE_VEHICLE.get(culture_id)
    return ShopPackage(
        key=f"plus_{culture_id}",
        nome=f"Pacchetto Plus — {nome}",
        desc=f"2 piloti + 8 combattenti + 1 vettore (skin {nome})",
        price_eur=5.00,
        pilots=2,
        fighters=8,
        vehicle=veh,
        cultura=culture_id,
        package_type="plus",
    )


PACKAGES: dict[str, ShopPackage] = {
    p.key: p
    for p in [
        _plus("nordamericana", "Nordamericana"),
        _plus("europea",       "Europea"),
        _plus("cinese",        "Cinese"),
        _plus("africana",      "Africana"),
        _plus("indiana",       "Indiana"),
        _plus("pacifica",      "Pacifica"),
        _plus("latinoamericana", "Latinoamericana"),
        _plus("lunare",        "Lunare"),
        _plus("cyber",         "Cyber"),
        _plus("non_tecnologica", "Non Tecnologica"),
        ShopPackage(
            key="plus_core",
            nome="Pacchetto Core — IA Delpy",
            desc="4 piloti + 6 combattenti + 1 vettore skin Delpy",
            price_eur=5.00,
            pilots=4,
            fighters=6,
            vehicle=("Belisario", "mission"),
            cultura=None,
            package_type="plus",
        ),
        ShopPackage(
            key="ticket_pro",
            nome="Ticket Server Pro",
            desc="Crea un server Pro da 256 agenzie; tutti ricevono un Pacchetto Plus al Giorno 1",
            price_eur=10.00,
            package_type="ticket_pro",
        ),
        ShopPackage(
            key="ticket_campioni",
            nome="Ticket Server Campioni",
            desc="Server élite ×4, Taglio ogni 10 giorni, ~40 giorni campagna (solo vincitori certificati)",
            price_eur=100.00,
            package_type="ticket_campioni",
        ),
    ]
}
