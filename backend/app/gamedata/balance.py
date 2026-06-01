"""Costanti di bilanciamento — GDD §9.4, §9.7, §11.

Calibrate con il pass Monte Carlo (§9.4). Parametrizzate per consentire
il ri-tuning (vedi questione aperta k_luna in §14 / Sviluppo.md §8).
"""
from __future__ import annotations

# --- §9.4 Modello del nemico ---
E_BASE = 100             # indice di forza iniziale
PHASE_A_SLOPE = 4        # E(t) = 100 + 4t per t in [0,60]
PHASE_A_END = 60
PHASE_B_DAILY = 1.0371   # composto giornaliero (~+3.71%/g == x1.2 ogni 5 g)

# coefficienti di combattimento (§9.4)
K_SBARCO = 1.0
K_INT = 1.0
K_LUNA = 1.5             # questione aperta: 1.5 vs 2.0 (§14)

# fattore casuale esito (§9.5)
RANDOM_MIN = 0.75
RANDOM_MAX = 1.25

# --- §9.7 Moltiplicatori ricompensa per tipo ---
REWARD_MULT_TERRESTRE = 1.0
REWARD_MULT_INTERCETTAZIONE = 1.2
REWARD_MULT_LUNARE = 1.5

# moltiplicatori allarme (§9.2 / §9.7)
ALARM_MULT_VERDE = 1.0
ALARM_MULT_GIALLO = 0.90
ALARM_MULT_ROSSO = 0.50
TRANSFER_SOLVER_SHARE = 0.25  # a chi svolge una missione trasferita

# --- §9.1 Assegnazione missioni ---
MISSIONS_PER_PLAYER = 4
MISSION_CAP_PER_PLAYER = 11
INACTIVE_AFTER_HOURS = 48

# --- §9.2 Allarme: scadenze ---
ALARM_VERDE_DAYS = 7
ALARM_ROSSO_DAY = 12
ALARM_ROSSO_UG_RESOLVE_HOURS = 48

# --- §11 Classifica / Ciclo 40 giorni / Endgame ---
CYCLE_DAYS = 40
UG_CUT_FRACTION = 0.25       # 25% peggiore tagliato per ciclo
TRASPORTO_COLONI_VALUE = 25  # missioni equivalenti
ALLIANCE_MAX_MEMBERS = 28
ALLIANCE_MAX_COLONNELLI = 4
ALLIANCE_PHASE_THRESHOLD = 112  # <= 4x28 -> fase alleanza
ENDGAME_ALLIANCES = 3

# §10 Co-finanziamento UG
UG_COFINANCE_PER_MISSION = 100

# velocita simulazione Server Campioni (§ doc Shop)
SPEED_STANDARD = 1
SPEED_CAMPIONI = 4
CAMPIONI_CYCLE_DAYS = 10
