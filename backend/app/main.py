"""Applicazione FastAPI SX2128."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin, admin_dashboard, agency, alliances_api, auth, buildings, catalog,
    chat_api, classifica_api, missions_api, personnel, shop_api, vehicles_api,
)
from app.database import init_db
from app.services.superadmin import ensure_superadmin


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_superadmin()
    yield


app = FastAPI(
    title="SX2128",
    description="Backend del gioco strategico competitivo asincrono SX2128.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "game": "SX2128"}


app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(agency.router)
app.include_router(catalog.router)
app.include_router(buildings.router)
app.include_router(personnel.router)
app.include_router(vehicles_api.router)
app.include_router(missions_api.router)
app.include_router(alliances_api.router)
app.include_router(chat_api.router)
app.include_router(classifica_api.router)
app.include_router(shop_api.router)
app.include_router(admin_dashboard.router)
