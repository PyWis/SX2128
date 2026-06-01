"""Applicazione FastAPI SX2128."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, agency, auth, buildings, catalog, missions_api, personnel, vehicles_api
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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
