"""Dashboard di controllo superadmin — gestione utenti, server, statistiche globali."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_superadmin
from app.models.core import Agency, Server, User
from app.services import superadmin as svc

router = APIRouter(prefix="/api/superadmin", tags=["superadmin"])


@router.get("/stats")
def global_stats(db: Session = Depends(get_db),
                 _: User = Depends(get_superadmin)) -> dict:
    """Statistiche globali: utenti, server, revenue, Agenda 2030."""
    return svc.get_global_stats(db)


@router.get("/users")
def list_users(search: str = "", limit: int = 100,
               db: Session = Depends(get_db),
               _: User = Depends(get_superadmin)) -> list:
    """Lista utenti con conteggi agenzia e missioni. Filtrabile per email."""
    return svc.list_users(db, search=search, limit=limit)


@router.get("/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db),
             _: User = Depends(get_superadmin)) -> dict:
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "utente non trovato")
    return svc._user_row(db, u)


@router.post("/users/{user_id}/ban")
def ban_user(user_id: int, db: Session = Depends(get_db),
             admin: User = Depends(get_superadmin)) -> dict:
    """Banna un utente (non superadmin)."""
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "utente non trovato")
    if u.is_superadmin:
        raise HTTPException(400, "impossibile bannare un superadmin")
    if u.id == admin.id:
        raise HTTPException(400, "impossibile auto-bannarsi")
    u.is_banned = True
    db.commit()
    return {"id": u.id, "email": u.email, "is_banned": True}


@router.post("/users/{user_id}/unban")
def unban_user(user_id: int, db: Session = Depends(get_db),
               _: User = Depends(get_superadmin)) -> dict:
    """Riabilita un utente bannato."""
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "utente non trovato")
    u.is_banned = False
    db.commit()
    return {"id": u.id, "email": u.email, "is_banned": False}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db),
                admin: User = Depends(get_superadmin)) -> dict:
    """Elimina un utente e tutte le sue agenzie."""
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "utente non trovato")
    if u.is_superadmin:
        raise HTTPException(400, "impossibile eliminare un superadmin")
    if u.id == admin.id:
        raise HTTPException(400, "impossibile auto-eliminarsi")
    db.query(Agency).filter(Agency.user_id == u.id).delete()
    db.delete(u)
    db.commit()
    return {"deleted": user_id}


@router.get("/servers")
def list_servers(db: Session = Depends(get_db),
                 _: User = Depends(get_superadmin)) -> list:
    """Lista di tutti i server con statistiche."""
    return svc.list_servers(db)


@router.delete("/servers/{server_id}")
def delete_server(server_id: int, db: Session = Depends(get_db),
                  _: User = Depends(get_superadmin)) -> dict:
    """Elimina un server (e le sue agenzie). Solo se terminato o vuoto."""
    s = db.get(Server, server_id)
    if not s:
        raise HTTPException(404, "server non trovato")
    agency_count = db.query(Agency).filter(Agency.server_id == server_id).count()
    if not s.finished and agency_count > 0:
        raise HTTPException(400, "eliminazione negata: server attivo con agenzie. Terminarlo prima.")
    db.query(Agency).filter(Agency.server_id == server_id).delete()
    db.delete(s)
    db.commit()
    return {"deleted": server_id}
