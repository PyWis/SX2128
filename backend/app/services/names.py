"""Generazione nomi reclute per cultura — GDD §3.4.

Il 50% dei reclutati ha nomi della cultura finanziata, il 50% di altre culture (§1).
Pool sintetico ma plausibile per locale; ampliabile senza toccare la logica.
"""
from __future__ import annotations

import random as _random

from app.gamedata.cultures import CULTURES, get_culture
from app.gamedata.enums import CultureId

Rng = _random.Random

# pool minimale per locale (nome dato); i cognomi sono generati per alcune culture
_FIRST: dict[str, list[str]] = {
    "inglese": ["James", "Emily", "Michael", "Sarah", "David", "Laura"],
    "francese": ["Lucas", "Camille", "Hugo", "Manon", "Louis", "Chloe"],
    "spagnolo": ["Mateo", "Sofia", "Diego", "Lucia", "Pablo", "Valeria"],
    "portoghese": ["Joao", "Beatriz", "Tiago", "Ines", "Rui", "Mariana"],
    "italiano": ["Marco", "Giulia", "Luca", "Chiara", "Matteo", "Sara"],
    "polacco": ["Jakub", "Zofia", "Piotr", "Maja", "Krzysztof", "Lena"],
    "olandese": ["Daan", "Sanne", "Sem", "Lotte", "Bram", "Anouk"],
    "tedesco": ["Lukas", "Hanna", "Felix", "Lena", "Jonas", "Mia"],
    "arabo": ["Omar", "Layla", "Yusuf", "Amira", "Karim", "Salma"],
    "swahili": ["Juma", "Amani", "Baraka", "Zuri", "Jabari", "Imani"],
    "yoruba": ["Ade", "Folake", "Tunde", "Yemi", "Bola", "Sade"],
    "amarico": ["Dawit", "Selam", "Abebe", "Tigist", "Yonas", "Hanna"],
    "indo_pakistano": ["Arjun", "Priya", "Rohan", "Aisha", "Vikram", "Neha"],
    "iraniano": ["Reza", "Yasmin", "Kaveh", "Darya", "Omid", "Roya"],
    "russo": ["Ivan", "Olga", "Dmitri", "Anya", "Sergei", "Katya"],
    "cinese": ["Wei", "Mei", "Hao", "Lin", "Jun", "Xia"],
    "giapponese": ["Haruto", "Sakura", "Ren", "Yui", "Sota", "Aoi"],
    "coreano": ["Min-jun", "Seo-yeon", "Ji-ho", "Ha-eun", "Do-yun", "Su-bin"],
    "malese": ["Aiman", "Nurul", "Faris", "Siti", "Hakim", "Aisyah"],
    "filippino": ["Jose", "Maria", "Andres", "Liwayway", "Mateo", "Dalisay"],
    "europeo": ["Alex", "Nina", "Leon", "Eva", "Max", "Vera"],
    "mitologico": ["Odino", "Atena", "Horus", "Freya", "Apollo", "Iside"],
    "nickname": ["Vortex", "Nyx", "Glitch", "Echo", "Raven", "Zero"],
}

_SURNAMES: dict[str, list[str]] = {
    "astronauti": ["Gagarin", "Armstrong", "Tereshkova", "Aldrin", "Leonov", "Ride"],
}


def _pick_locale(distribuzione: dict[str, int], rng: Rng) -> str:
    locali = list(distribuzione.keys())
    pesi = list(distribuzione.values())
    return rng.choices(locali, weights=pesi, k=1)[0]


def generate_name(financed_culture: CultureId, rng: Rng) -> tuple[str, CultureId]:
    """Ritorna (nome_completo, cultura_di_origine)."""
    # 50% cultura finanziata, 50% altra cultura (§1)
    if rng.random() < 0.5:
        origin = financed_culture
    else:
        others = [c for c in CULTURES if c != financed_culture]
        origin = rng.choice(others)

    culture = get_culture(origin)
    locale = _pick_locale(culture.nomi, rng)
    first = rng.choice(_FIRST.get(locale, _FIRST["inglese"]))

    # regole cognome speciali (§3.4)
    if origin == CultureId.CYBER:
        return f"{first}{rng.randint(10, 99)}", origin
    if origin == CultureId.LUNARE:
        return f"{first} {rng.choice(_SURNAMES['astronauti'])}", origin
    if origin == CultureId.NON_TECNOLOGICA:
        return f"{first}", origin  # cognomi = nomi enclavi (placeholder)
    return f"{first}", origin
