"""Configurazione test: DB SQLite temporaneo condiviso, ricreato per ogni test."""
import os
import tempfile

# Imposta la URL del DB PRIMA di importare l'app (evita reload fragili)
_FD, _PATH = tempfile.mkstemp(suffix=".db")
os.close(_FD)
os.environ["SX2128_DATABASE_URL"] = f"sqlite:///{_PATH}"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine, init_db
from app.main import app


@pytest.fixture()
def client():
    # tabula rasa per ogni test
    Base.metadata.drop_all(bind=engine)
    init_db()
    with TestClient(app) as c:
        yield c


def pytest_sessionfinish(session, exitstatus):
    try:
        os.unlink(_PATH)
    except OSError:
        pass
