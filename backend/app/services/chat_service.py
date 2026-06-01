"""Chat asincrona — GDD §13."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.gamedata.enums import ChatChannelType
from app.models.core import Agency, ChatMessage

# §13 / §7 Anti-abuso: rate-limit messaggi per ora
RATE_LIMIT_UGNET = 20    # max messaggi/ora su UG-Net (slow-mode)
RATE_LIMIT_OTHER = 50    # max messaggi/ora su altri canali


def _dm_key(a: int, b: int) -> str:
    lo, hi = min(a, b), max(a, b)
    return f"{lo}-{hi}"


def _check_rate_limit(db: Session, agency: Agency, channel_type: str) -> None:
    limit = RATE_LIMIT_UGNET if channel_type == ChatChannelType.UG_NET.value else RATE_LIMIT_OTHER
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    count = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.author_agency_id == agency.id,
            ChatMessage.channel_type == channel_type,
            ChatMessage.created_at >= one_hour_ago,
        )
        .count()
    )
    if count >= limit:
        raise ValueError(
            f"rate limit superato: max {limit} messaggi/ora su {channel_type} (§13 anti-spam)"
        )


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

    _check_rate_limit(db, agency, channel_type)

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
