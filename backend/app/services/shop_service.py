"""Shop e monetizzazione anti-P2W — GDD §6 / doc Shop.

Regole:
- max 1 pacchetto Plus per ciclo di 40 giorni per agenzia (§5.19)
- max 1 acquisto/giorno per agenzia
- le unità entrano nel Pool di Riserva Premium (premium_pool_json)
- il pool si riscatta ai normali turni di reclutamento (non bypassa il limite)
- 10% del lordo → Agenda 2030 (tracciato in ShopTransaction.agenda_2030_eur)
"""
from __future__ import annotations

from datetime import date, timezone

from sqlalchemy.orm import Session

from app.gamedata.shop import AGENDA_2030_RATE, PACKAGES, ShopPackage
from app.models.core import Agency, Server, ShopTransaction


class ShopError(ValueError):
    pass


def _today_utc() -> date:
    from datetime import datetime
    return datetime.now(timezone.utc).date()


def _pool(agency: Agency) -> list[dict]:
    return list(agency.premium_pool_json or [])


def _set_pool(agency: Agency, pool: list[dict]) -> None:
    agency.premium_pool_json = pool if pool else None


def get_catalog() -> list[dict]:
    return [
        {
            "key": p.key, "nome": p.nome, "desc": p.desc,
            "price_eur": p.price_eur,
            "agenda_2030_eur": round(p.price_eur * AGENDA_2030_RATE, 2),
            "pilots": p.pilots, "fighters": p.fighters,
            "vehicle": {"project": p.vehicle[0], "vclass": p.vehicle[1]} if p.vehicle else None,
            "cultura": p.cultura, "package_type": p.package_type,
        }
        for p in PACKAGES.values()
    ]


def purchase(db: Session, agency: Agency, server: Server, package_key: str) -> ShopTransaction:
    """Acquista un pacchetto shop con validazione anti-P2W (§5.19)."""
    pkg = PACKAGES.get(package_key)
    if not pkg:
        raise ShopError(f"pacchetto sconosciuto: {package_key}")

    today = _today_utc()

    # Max 1 acquisto/giorno
    last = (
        db.query(ShopTransaction)
        .filter(ShopTransaction.agency_id == agency.id)
        .order_by(ShopTransaction.created_at.desc())
        .first()
    )
    if last and last.created_at.date() == today:
        raise ShopError("acquisto gia effettuato oggi (max 1/giorno, §5.19)")

    # Max 1 pacchetto Plus per ciclo
    if pkg.package_type == "plus":
        existing_cycle = (
            db.query(ShopTransaction)
            .filter(
                ShopTransaction.agency_id == agency.id,
                ShopTransaction.server_id == server.id,
                ShopTransaction.cycle_at_purchase == server.cycle,
                ShopTransaction.package_key.like("plus_%"),
            )
            .first()
        )
        if existing_cycle:
            raise ShopError(
                f"hai gia acquistato un pacchetto Plus in questo ciclo (ciclo {server.cycle}, §5.19)"
            )

    agenda = round(pkg.price_eur * AGENDA_2030_RATE, 2)
    tx = ShopTransaction(
        agency_id=agency.id,
        server_id=server.id,
        package_key=package_key,
        price_eur=pkg.price_eur,
        agenda_2030_eur=agenda,
        cycle_at_purchase=server.cycle,
    )
    db.add(tx)

    # Pacchetti Plus: aggiunge unità al pool di riserva
    if pkg.package_type == "plus":
        pool = _pool(agency)
        for _ in range(pkg.pilots):
            pool.append({"unit_type": "pilot"})
        for _ in range(pkg.fighters):
            pool.append({"unit_type": "fighter"})
        if pkg.vehicle:
            pool.append({"unit_type": "vehicle", "project": pkg.vehicle[0], "vclass": pkg.vehicle[1]})
        _set_pool(agency, pool)

    return tx


def redeem_from_pool(db: Session, agency: Agency, unit_type: str,
                     rng) -> dict:
    """Riscatta 1 unità dal pool di riserva premium.

    Usa il normale slot di reclutamento giornaliero (recruited_today).
    unit_type: "pilot" | "fighter" | "vehicle"
    """
    from app.gamedata.enums import CultureId
    from app.models.core import Fighter, Pilot, Vehicle
    from app.services import formulas as F
    from app.services.names import generate_name
    from app.gamedata.cultures import get_culture

    if agency.recruited_today and unit_type != "vehicle":
        raise ShopError("reclutamento gia effettuato oggi (max 1/giorno, §3)")

    pool = _pool(agency)
    # trova prima occorrenza del tipo richiesto
    idx = next((i for i, u in enumerate(pool) if u["unit_type"] == unit_type), None)
    if idx is None:
        raise ShopError(f"nessuna unita '{unit_type}' nel pool di riserva")

    item = pool.pop(idx)
    _set_pool(agency, pool)

    culture = get_culture(agency.culture)

    if unit_type == "pilot":
        from app.services.recruitment import _count_units
        if _count_units(agency) + 1 > agency.barracks_capacity:
            raise ShopError("capacita caserma insufficiente")
        name, origin = generate_name(CultureId(agency.culture), rng)
        licenses = {}
        if "native_d_bronze" in culture.perks:
            licenses["D"] = "bronze"
        p = Pilot(
            agency_id=agency.id, name=name, origin_culture=origin.value,
            espo_pct=F.roll_pilot_stat(rng),
            str_pct=F.roll_pilot_stat(rng),
            strs_pct=F.roll_pilot_stat(rng),
            licenses=licenses,
        )
        db.add(p)
        db.flush()
        agency.recruited_today = True
        return {"unit_type": "pilot", "id": p.id, "name": p.name}

    elif unit_type == "fighter":
        from app.services.recruitment import _count_units
        if _count_units(agency) + 1 > agency.barracks_capacity:
            raise ShopError("capacita caserma insufficiente")
        name, origin = generate_name(CultureId(agency.culture), rng)
        stats = F.roll_fighter_stats(rng)
        strv = stats["STR"]
        if "native_str_+30" in culture.perks and origin.value == agency.culture:
            strv = int(round(strv * 1.3))
        f = Fighter(
            agency_id=agency.id, name=name, origin_culture=origin.value,
            vit=stats["VIT"], strg=strv, dif=stats["DIF"],
            mov=stats["MOV"], spa=stats["SPA"],
        )
        db.add(f)
        db.flush()
        agency.recruited_today = True
        return {"unit_type": "fighter", "id": f.id, "name": f.name, "tabi": f.tabi}

    elif unit_type == "vehicle":
        # Veicoli del pool vanno direttamente in hangar (non usano slot reclutamento)
        used_slots = sum(1 for v in agency.vehicles if v.status != "eliminated")
        if used_slots >= agency.hangar_slots:
            raise ShopError("hangar al completo")
        project = item.get("project", "Belisario")
        vclass = item.get("vclass", "mission")
        v = Vehicle(agency_id=agency.id, project=project, vclass=vclass, status="barracks")
        db.add(v)
        db.flush()
        return {"unit_type": "vehicle", "id": v.id, "project": project, "vclass": vclass}

    raise ShopError(f"tipo unita sconosciuto: {unit_type}")


def get_transactions(db: Session, agency_id: int) -> list[dict]:
    txs = (
        db.query(ShopTransaction)
        .filter(ShopTransaction.agency_id == agency_id)
        .order_by(ShopTransaction.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": t.id, "package_key": t.package_key,
            "price_eur": t.price_eur, "agenda_2030_eur": t.agenda_2030_eur,
            "cycle_at_purchase": t.cycle_at_purchase,
            "created_at": t.created_at.isoformat(),
        }
        for t in txs
    ]
