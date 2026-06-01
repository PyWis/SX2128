"""Configurazione applicazione (env-driven)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SX2128_", env_file=".env", extra="ignore")

    app_name: str = "SX2128"
    # Default SQLite per sviluppo locale; in produzione usare PostgreSQL via env.
    database_url: str = "sqlite:///./sx2128.db"
    secret_key: str = "dev-secret-change-me"  # override in produzione
    access_token_minutes: int = 60 * 24 * 7
    # Numero massimo di agenzie per shard (Piano Tanaka, §worldbuilding / GDD)
    server_capacity: int = 256


@lru_cache
def get_settings() -> Settings:
    return Settings()
