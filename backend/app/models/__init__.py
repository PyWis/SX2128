"""Registro dei modelli SQLAlchemy."""
from app.models.core import (  # noqa: F401
    Agency,
    Alliance,
    ChatMessage,
    Fighter,
    Loan,
    Mission,
    Pilot,
    Server,
    User,
    Vehicle,
)

__all__ = [
    "Agency", "Alliance", "ChatMessage", "Fighter", "Loan", "Mission",
    "Pilot", "Server", "User", "Vehicle",
]
