"""Chat asincrona — GDD §13."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.gamedata.enums import ChatChannelType
from app.models.core import Agency, ChatMessage


def _dm_key(a: int, b: int) -> str:
    lo, hi = min(a, b), max(a, b)
    return f"{lo}-{hi}"


def send_message(db: Session, agency: Agency, channel_type: str,
                 channel_key: str, body: str) -> ChatMessage:
    body = body.strip()
    if not body:
        raise ValueError("messaggio vuoto")
    if len(body) > 4000:
        raise ValueError("messaggio troppo lungo (max 4000 caratteri)")

    ctype = ChatChannelType(channel_type)

    if ctype == ChatChannelType.ALLEANZA:
        if not agency.alliance_id or str(agency.alliance_id) != channel_key:
            raise ValueError("non sei in questa alleanza")

    elif ctype == ChatChannelType.CULTURA:
        if agency.culture != channel_key:
            raise ValueError("non appartieni a questa cultura")

    elif ctype == ChatChannelType.DM:
        parts = channel_key.split("-")
        if len(parts) != 2 or str(agency.id) not in parts:
            raise ValueError("chiave DM non valida")

    elif ctype == ChatChannelType.DELPY:
        raise ValueError("canale Delpy e di sola lettura")

    msg = ChatMessage(
        server_id=agency.server_id,
        channel_type=channel_type,
        channel_key=channel_key,
        author_agency_id=agency.id,
        body=body,
    )
    db.add(msg)
    return msg


def post_delpy(db: Session, server_id: int, body: str) -> ChatMessage:
    """Messaggio di sistema dal canale Delpy (author = NULL)."""
    msg = ChatMessage(
        server_id=server_id,
        channel_type=ChatChannelType.DELPY.value,
        channel_key="sistema",
        author_agency_id=None,
        body=body,
    )
    db.add(msg)
    return msg


def get_messages(db: Session, server_id: int, channel_type: str,
                 channel_key: str, limit: int = 50) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(
            ChatMessage.server_id == server_id,
            ChatMessage.channel_type == channel_type,
            ChatMessage.channel_key == channel_key,
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
