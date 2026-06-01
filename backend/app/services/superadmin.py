"""Bootstrap superadmin e servizi dashboard."""
from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.core import Agency, Server, ShopTransaction, User
from app.security import hash_password

SUPERADMIN_EMAIL = "delpyadmin@sx2128.local"


def ensure_superadmin() -> None:
    """Crea o aggiorna il superadmin delpyadmin all'avvio; stampa la password sul terminale."""
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == SUPERADMIN_EMAIL).first()
        if user is None:
            password = secrets.token_urlsafe(16)
            user = User(
                email=SUPERADMIN_EMAIL,
                hashed_password=hash_password(password),
                is_superadmin=True,
            )
            db.add(user)
            db.commit()
            _print_credentials(password, created=True)
        elif not user.is_superadmin:
            user.is_superadmin = True
            db.commit()
    finally:
        db.close()


def reset_superadmin_password() -> str:
    """Rigenera la password del superadmin e la ritorna in chiaro (uso CLI)."""
    password = secrets.token_urlsafe(16)
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == SUPERADMIN_EMAIL).first()
        if user:
            user.hashed_password = hash_password(password)
            db.commit()
    finally:
        db.close()
    return password


def _print_credentials(password: str, created: bool = True) -> None:
    verb = "CREATO" if created else "AGGIORNATO"
    border = "=" * 60
    print(f"\n{border}")
    print(f"  SX2128 · Superadmin {verb}")
    print(f"  Utente : {SUPERADMIN_EMAIL}")
    print(f"  Password: {password}")
    print(f"  Dashboard: /admin.html")
    print(f"{border}\n", flush=True)


# ─── Query per la dashboard ───────────────────────────────────────────────────

def list_users(db: Session, search: str = "", limit: int = 100) -> list[dict]:
    q = db.query(User)
    if search:
        q = q.filter(User.email.ilike(f"%{search}%"))
    users = q.order_by(User.created_at.desc()).limit(limit).all()
    return [_user_row(db, u) for u in users]


def _user_row(db: Session, u: User) -> dict:
    agency_count = db.query(Agency).filter(Agency.user_id == u.id).count()
    missions_total = (
        db.query(Agency).filter(Agency.user_id == u.id)
        .with_entities(Agency.missions_completed)
        .all()
    )
    missions_sum = sum(r[0] for r in missions_total)
    return {
        "id": u.id,
        "email": u.email,
        "is_superadmin": u.is_superadmin,
        "is_banned": u.is_banned,
        "created_at": u.created_at.isoformat(),
        "agency_count": agency_count,
        "missions_completed": missions_sum,
    }


def get_global_stats(db: Session) -> dict:
    total_users = db.query(User).count()
    banned_users = db.query(User).filter(User.is_banned == True).count()  # noqa: E712
    total_servers = db.query(Server).count()
    active_servers = db.query(Server).filter(Server.finished == False).count()  # noqa: E712
    total_agencies = db.query(Agency).count()
    total_revenue = db.query(ShopTransaction).with_entities(
        ShopTransaction.price_eur
    ).all()
    revenue_eur = round(sum(r[0] for r in total_revenue), 2)
    agenda_2030 = db.query(ShopTransaction).with_entities(
        ShopTransaction.agenda_2030_eur
    ).all()
    agenda_eur = round(sum(r[0] for r in agenda_2030), 2)
    return {
        "total_users": total_users,
        "banned_users": banned_users,
        "total_servers": total_servers,
        "active_servers": active_servers,
        "total_agencies": total_agencies,
        "revenue_eur": revenue_eur,
        "agenda_2030_eur": agenda_eur,
    }


def list_servers(db: Session) -> list[dict]:
    servers = db.query(Server).order_by(Server.started_at.desc()).all()
    result = []
    for s in servers:
        agency_count = db.query(Agency).filter(Agency.server_id == s.id).count()
        result.append({
            "id": s.id,
            "name": s.name,
            "server_type": s.server_type,
            "speed": s.speed,
            "current_day": s.current_day,
            "cycle": s.cycle,
            "capacity": s.capacity,
            "agency_count": agency_count,
            "finished": s.finished,
            "started_at": s.started_at.isoformat(),
        })
    return result
