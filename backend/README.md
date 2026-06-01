# SX2128 — Backend

Backend del gioco strategico competitivo asincrono **SX2128** (FastAPI + SQLAlchemy).
Implementa il motore di gioco descritto in [`../Sviluppo.md`](../Sviluppo.md) e nel GDD.

## Stato (fasi di `Sviluppo.md`)

- **F0 — Fondamenta**: ✅ stack, auth JWT, DB/ORM, modello server/shard (256 agenzie), seed dati statici, stato iniziale agenzia (§0.2).
- **F1 — Tick & Economia**: ✅ tick giornaliero (§0.1), fedeltà lineare (§1), bilancio/default (§2), reclutamento (§3), assegnazione missioni base + scaling nemico E(t) (§9.1/§9.4), co-finanziamento UG (§10).
- **F2–F7**: in corso (vedi `Sviluppo.md`).

## Avvio

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://localhost:8000
# Documentazione interattiva: http://localhost:8000/docs
```

Di default usa SQLite locale (`sqlite:///./sx2128.db`). Per PostgreSQL impostare
`SX2128_DATABASE_URL`. Altre variabili: `SX2128_SECRET_KEY`, `SX2128_DATABASE_URL`.

## Test

```bash
cd backend
python -m pytest -q
```

I test coprono le formule core (combattimento, scaling, statistiche, economia — `tests/test_formulas.py`)
e il flusso end-to-end auth → server → agenzia → reclutamento → tick (`tests/test_api.py`).

## Struttura

```
app/
  gamedata/     # tabelle statiche del GDD (culture, vettori, equip, licenze, bilanciamento)
  models/       # entità SQLAlchemy
  services/     # logica di gioco (formule, economia, reclutamento, tick, missioni)
  api/          # router FastAPI (auth, agency, admin, catalog)
  main.py       # app FastAPI
tests/
```

## API principali (slice attuale)

| Metodo | Path | Descrizione |
|---|---|---|
| POST | `/api/auth/register` · `/api/auth/login` | account + token JWT |
| POST | `/api/admin/server` | crea uno shard di gioco |
| POST | `/api/admin/server/{id}/tick` | avanza di un giorno (in prod: worker schedulato) |
| POST | `/api/agency` | fonda l'agenzia (stato iniziale §0.2) |
| GET  | `/api/agency/{server_id}` | stato agenzia (marca attività §9.1) |
| POST | `/api/agency/{server_id}/recruit` | reclutamento (§3, max 1/giorno) |
| GET  | `/api/catalog/*` | dati statici (culture, vettori, equip, licenze, opzioni recluta) |

Il frontend SPA di prova è in [`../frontend/`](../frontend/) (apri `index.html` e punta l'API base al backend).
