"""API Chat — GDD §13."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.core import Agency, User
from app.services import chat_service as svc

router = APIRouter(prefix="/api/chat", tags=["chat"])


class SendMessageRequest(BaseModel):
    channel_type: str
    channel_key: str
    body: str


def _my_agency(db: Session, user: User, server_id: int) -> Agency:
    a = db.query(Agency).filter(
        Agency.user_id == user.id, Agency.server_id == server_id,
    ).first()
    if not a:
        raise HTTPException(404, "agenzia non trovata")
    return a


@router.post("/{server_id}/messages")
def send_message(server_id: int, payload: SendMessageRequest,
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    agency = _my_agency(db, user, server_id)
    try:
        msg = svc.send_message(db, agency, payload.channel_type, payload.channel_key, payload.body)
    except ValueError as e:
        raise HTTPException(400, str(e))
    db.commit()
    db.refresh(msg)
    return {
        "id": msg.id,
        "channel_type": msg.channel_type,
        "channel_key": msg.channel_key,
        "author_agency_id": msg.author_agency_id,
        "body": msg.body,
        "created_at": msg.created_at.isoformat(),
    }


@router.get("/{server_id}/messages/{channel_type}/{channel_key}")
def get_messages(server_id: int, channel_type: str, channel_key: str,
                 limit: int = 50, db: Session = Depends(get_db),
                 _: User = Depends(get_current_user)) -> list[dict]:
    msgs = svc.get_messages(db, server_id, channel_type, channel_key, limit=limit)
    return [
        {
            "id": m.id,
            "channel_type": m.channel_type,
            "channel_key": m.channel_key,
            "author_agency_id": m.author_agency_id,
            "body": m.body,
            "created_at": m.created_at.isoformat(),
        }
        for m in reversed(msgs)  # cronologico
    ]
