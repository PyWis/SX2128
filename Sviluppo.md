# Sviluppo — SX2128

> Documento di sviluppo operativo. Raccoglie i **task** necessari a realizzare il gioco
> descritto nei tre documenti di design:
>
> - **Worldbuilding 2128 — Edizione Integrata v8** (lore, ambientazione, personaggi)
> - **Main Programma — GDD Integrato v3** (regole, sistemi, tabelle) — fonte primaria delle meccaniche
> - **Pianificazione Strategica Monetizzazione ed Ecosistema Shop** (economia reale, shop, Server Campioni)
>
> I riferimenti tipo `§9.5` puntano ai paragrafi del GDD. Lo stato attuale del repository è
> il solo **sito vetrina** (`index.html`, `story.html`, `game.html`, `contatti.html` + `assets/`):
> il gioco vero e proprio è **da costruire da zero**.

---

## 1. Sintesi del prodotto

SX2128 è un **gioco strategico competitivo asincrono** per browser. Il giocatore è uno dei
**256 generali** nominati dal Patto del Primo Luglio (1 luglio 2128) e guida un'**Agenzia di Difesa**
nella guerra contro la flotta aliena ("Oggetto Sigma"). Caratteristiche portanti:

- **Tick giornaliero**: il mondo avanza una volta al giorno (§0.1). Non è un real-time game.
- **Server a vita finita** (~160–200 giorni) con **endgame** a 3 alleanze superstiti (§11.1).
- **Economia a risorsa R** auto-regolante: il reddito scala con la forza del nemico `E(t)` (§9.4, §9.7).
- **Motore di attrito**: il nemico cresce in modo composto in Fase B e finisce per superare la singola
  agenzia, spingendo alla cooperazione in **alleanze** (§9.4, §12).
- **Multiplayer asincrono**: classifica, chat persistente, alleanze, trasferimento missioni.
- **Monetizzazione etica anti-P2W** + ecosistema Phygital (shop digitale/fisico, Server Campioni).

L'IA narrativa **Delpy** è il canale di sistema/notifiche (§13) e il "volto" dello shop.

---

## 2. Architettura tecnica proposta

> Proposta di riferimento; da confermare in fase F0. Il vincolo non negoziabile è che il
> gioco è **server-authoritative** (il tick e la risoluzione combattimento NON girano sul client).

| Layer | Proposta | Note |
|---|---|---|
| Frontend | SPA (es. React/Vite o Svelte) sopra l'attuale estetica `assets/css/style.css` | Riusare font Orbitron/Rajdhani/JetBrains Mono e palette del sito |
| Backend | API REST/GraphQL (es. Node/TypeScript o Python/FastAPI) | Stateless dietro auth |
| Database | Relazionale (PostgreSQL) | Transazioni forti sull'economia; vincoli di integrità |
| Job scheduler | Worker per il **tick giornaliero** + scadenze allarmi/cicli | Idempotente, ripartibile |
| Realtime/chat | WebSocket o polling per i badge non-letti; chat è **async-first** (§13) | Persistenza messaggi |
| Auth | Account giocatore + sessione; ruoli (giocatore, capoalleanza, colonnello, admin) | |
| Deploy/CI | Pipeline build + test + deploy; ambienti staging/prod | |

**Decisione chiave da prendere in F0**: modello server/shard — se le 256 agenzie sono per singolo
shard e come si istanziano i server F2P / Pro / Campioni (vedi §14 "Monetizzazione e modello server/shard", ancora aperta).

---

## 3. Modello dati (entità principali)

Task trasversale: definire schema e migrazioni per le entità sotto. Tutte le quantità economiche in **R**.

- **Server/Shard** — tipo (F2P / Pro / Campioni), velocità simulazione (×1 / ×4), giorno corrente, data inizio, stato ciclo.
- **Player/Agenzia** — utente, cultura finanziata, giorni di fedeltà, base scelta (coordinate), saldo R, ultimo login, stato (attivo/inattivo/tagliato), capacità edifici.
- **Cultura** — tabella statica delle 10 culture (base R/g, fedeltà %/g, vantaggio) (§1.1).
- **Prestito** — tipo (Cultura/UG), importo, rate residue, slot, stato default (§2.2–2.3).
- **Pilota** — ESPO%, STR%, STRS%, licenze possedute (A/B/C/D/E × livello), stato (libero/in volo/in addestramento), stipendio (§3.2, §4.2–4.3).
- **Combattente** — VIT, STR, DIF, MOV, SPA, TABI, esperienza/missioni, stelle, stipendio, stato (caserma/ospedale/in volo/eliminato) (§3.3, §4.4–4.5).
- **Equipaggiamento** — armi/armatura terrestre/armatura spaziale per livello (§6.1); inventario agenzia.
- **Missile** — livello terrestre/spaziale (§6.2); consumabile.
- **Vettore** — tipo (esplorazione/caccia/missione/spazio-caccia/spazio-missione/civile), progetto, licenza richiesta, costo, manutenzione, stat (ESPO/Attacco/Velocità/Postazioni/Capacità H), pilota assegnato, stato (hangar/in volo + ETA) (§8.1–8.6).
- **Hangar** — slot sbloccati e prerequisiti (§7).
- **Missione** — tipo (Terrestre/Intercettazione Terrestre/Intercettazione Lunare/Lunare/UG/Evacuazione), coordinate o teatro, Pn, livello allarme (verde/giallo/rosso), giorno assegnazione, scadenza, assegnatario, stato, ricompensa (§9).
- **Sortie** — vettore, catena di tappe (missioni), pool missili, ETA, log risoluzione (§9.11).
- **Alleanza** — membri (≤28), capoalleanza, colonnelli (≤4), tesoreria comune, pool missioni comuni (§12).
- **Messaggio/Canale chat** — UG-Net, Cultura, Alleanza, DM, Thread Operazione UG, Delpy (§13).
- **Classifica/Ciclo** — punteggio (missioni completate), ESPO totale (spareggio), stato ciclo 40 giorni, eventi Taglio UG (§11).
- **Transazione Shop** — pacchetti, ticket, oggetti phygital, quota devoluzione 10% Agenda 2030 (doc Shop).

---

## 4. Roadmap a fasi

| Fase | Obiettivo | Esito verificabile |
|---|---|---|
| **F0 — Fondamenta** | Stack, auth, DB, deploy, scelta modello server | Si crea un account e si entra in un'agenzia vuota |
| **F1 — Tick & Economia** | Loop giornaliero, bilancio, prestiti, governo/fedeltà | Un'agenzia accredita/addebita correttamente ogni giorno |
| **F2 — Personale & Edifici** | Reclute, caserma, ospedale, magazzino, hangar | Si reclutano, addestrano, curano, equipaggiano unità |
| **F3 — Vettori & Missioni base (Terrestri)** | Vettori, assegnazione missioni, risoluzione combattimento, UI 5 schermate | Si lancia e risolve una missione terrestre dal giorno 1 |
| **F4 — Teatri completi** | Intercettazione aerea/lunare, sbarco lunare, evacuazione, sortie multi-missione, scaling E(t) | Tutti i tipi di missione sbloccano alle date previste |
| **F5 — Multiplayer & Endgame** | Classifica, co-finanziamento UG, ciclo 40 giorni, alleanze, chat, missioni UG | Un server completo arriva all'endgame a 3 alleanze |
| **F6 — Monetizzazione** | Shop digitale, ticket Pro, Server Campioni, sezione Phygital/Campioni, devoluzione 10% | Acquisti anti-P2W funzionanti e tracciati |
| **F7 — Bilanciamento & Hardening** | Pass Monte Carlo, anti-abuso, performance, QA | Coefficienti confermati, server reggono il carico |

Le epiche dettagliate (§5) sono raggruppate per sistema; ogni task riporta tra `[]` la fase consigliata.

### Stato di avanzamento

Lo scaffold full-stack è avviato in [`backend/`](backend/) (Python · FastAPI · SQLAlchemy) e
[`frontend/`](frontend/) (SPA vanilla coerente col sito). Stato corrente:

- **F0 — Fondamenta**: ✅ stack scelto, auth JWT, DB/ORM + modelli, modello server/shard (256 agenzie),
  seed dati statici (10 culture, 53 vettori, equip, missili, licenze, prestiti), stato iniziale agenzia (§0.2).
- **F1 — Tick & Economia**: ✅ tick giornaliero (§0.1), fedeltà lineare con reset (§1), flussi di bilancio +
  default (§2), reclutamento con perk culturali (§3), assegnazione missioni + scaling nemico `E(t)` (§9.1/§9.4),
  formule di combattimento/ricompensa testate (§9.5–9.7), co-finanziamento UG (§10).
- **F2 — Personale & Edifici**: ✅ upgrade caserma/ospedale/hangar con prerequisiti (§4.1, §5.1, §7);
  addestramento licenze pilota con progressione tier + perk Europea (§4.2); addestramento stat pilota e
  combattenti (§4.3, §4.4); gestione ospedale (ricovero/dimissione + guarigione nel tick §5.2);
  acquisto vettori con sconti culturali + verifica slot hangar (§8); assegnazione pilota↔vettore con
  controllo licenze (§8); equipaggiamento combattenti 3 slot (§6.1); carica missili su vettori da caccia
  (§6.2); completamento addestramenti nel tick; SPA vanilla con tabs. Test: 49 verdi (`backend/tests/`).
- **F3 — Vettori & Missioni base (Terrestri)**: ✅ acquisto vettori con sconti culturali; assegnazione pilota↔vettore con controllo licenze; calcolo ETA haversine andata+ritorno (§8); lancio missione con validazione tipo vettore/stato/pilota/combattenti (§9.10); risoluzione combattimento nel tick: Pg sbarco (ΣTABI+equip) e intercettazione (attacco+missili×stat%), fattore casuale ±25%, danni VIT ripartiti per DIF, eliminazione vettore+pilota, consumo equip 30%, reset missili (§9.5–9.7); premi accreditati all'agenzia; simulatore Pg vs Pn ±25% + stima probabilità (§9.10); tab Missioni frontend con plancia, dialog lancio+simula, in-volo ETA, storico combat log. Test: 62 verdi (`backend/tests/`).
- **F4 — Teatri completi**: ✅ escalation allarmi Verde→Giallo→Rosso→UG_risolve nel tick (§9.2); ESPO giornaliero da aeroplani da esplorazione stazionati con pilota (§8.1); missioni EVACUAZIONE civili con spazioplani civili, ricompensa = min(capacita_H, civili) × tariffa (§9.9); overhead lunare fisso ±6gg round-trip per missioni spaziali (§8.5); sortie multi-missione a catena (max 4 tappe), ETA cumulativo haversine waypoint-to-waypoint, consumo equip/missili solo sull'ultima tappa, chain interrotta su sconfitta intercettazione (§9.11); sblocco tipi missione per giorno di server (§9.3); frontend: badge allarme colorati, info evacuazione, dialog lancio con selezione catena. Test: 76 verdi (`backend/tests/`).
- **F5 — Multiplayer & Endgame**: ✅ classifica agenzie per missioni completate + spareggio ESPO (§11); ciclo 40 giorni con Taglio UG 25% peggiore + bonus Trasporto Coloni +25 missioni al top 50% (§11); notifica Delpy automatica al Taglio; alleanze (crea/entra/lascia, max 28 membri, 4 colonnelli, tesoreria comune deposito/prelievo, promozione) (§12); trasferimento missione Verde al pool alleanza con split ricompensa 25/75% al rientro (§12); missioni UG ad alto rischio generate ogni 5 giorni dal giorno 30, visibili a tutti, reward 2× (§9.8); split ricompensa missioni trasferite nel tick (TRANSFER_SOLVER_SHARE); chat asincrona con canali UG-Net, Cultura, Alleanza, DM, Delpy sistema (§13); frontend: tab Classifica, tab Alleanze, tab Chat con messaggi Delpy e UG-Net. Test: 99 verdi.
- **F6 — Monetizzazione**: ✅ catalogo shop: 11 Pacchetti Plus (10 cultura + 1 Core/IA) a 5€ + Ticket Server Pro (10€) + Ticket Campioni (100€); anti-P2W Soluzione C: max 1 pacchetto Plus/ciclo + max 1/giorno; unità nel Pool di Riserva Premium, riscatto ai turni normali di reclutamento (non bypassa limite §5.19); riscatto vettori direttamente all'hangar; tracciabilità Agenda 2030 10% su ogni transazione; storico acquisti per ciclo; Server Campioni ciclo ogni 10 giorni (CAMPIONI_CYCLE_DAYS); Delpy §5.20: notifiche narrate sblocco missioni, pre-Taglio 5gg, saldo negativo, rientro sortie; frontend: tab Shop con catalogo card, pool riserva, riscatto, storico transazioni con quota Agenda 2030. Test: 120 verdi.
- **F7 — Bilanciamento & Hardening**: ✅ motore Monte Carlo (combat_simulation, breakeven_pg, income_band_report, k_luna_analysis) con 200k prove/scenario; API admin `/api/admin/montecarlo/*` (simulate, breakeven, income-band, k-luna); chat rate-limit §13 anti-spam (20 msg/ora UG-Net, 50 altri canali); formule unit test completi (E(t), ricompense, combattimento, esperienza, cofinanziamento); k_luna=1.5 confermato (win_rate luna < terra al giorno 60). Test: 153 verdi.

---

## 5. Epiche e task per sistema

### 5.0 Fondamenta (F0)

- [ ] **Setup repository gioco**: separare l'app di gioco dal sito vetrina; scaffolding frontend + backend + DB. `[F0]`
- [ ] **Definire e configurare lo stack** scelto (§2) con ambienti staging/prod e pipeline CI. `[F0]`
- [ ] **Autenticazione e account giocatore**: registrazione, login, sessione, ruoli. `[F0]`
- [ ] **Modello server/shard** e onboarding al server (scelta da §14): istanziazione di un server da 256 slot. `[F0]`
- [ ] **Schema DB + migrazioni** per le entità di §3. `[F0]`
- [ ] **Seed dati statici**: tabelle Culture (§1.1), Vettori (§8.1–8.6), Equipaggiamento (§6.1), Missili (§6.2), Licenze (§4.2), costi upgrade (§4.1, §5.1, §7), prestiti (§2.2). `[F0]`
- [ ] **Stato iniziale agenzia** (§0.2): capitale **2.000 R**, caserma 10 posti, ospedale 2 posti, hangar 3 slot, **Licenza A-Bronze gratuita** allo start. `[F0]`

### 5.1 Motore del tick giornaliero (F1) — §0.1

- [ ] **Job di tick giornaliero** server-authoritative, idempotente e ripartibile, parametrizzato per **velocità simulazione** (×1 standard, ×4 Campioni). `[F1]`
- [ ] Sequenza tick (§0.1): accredito contributo fazione + co-finanziamento UG → addebito manutenzione/rate/stipendi/addestramento → aggiorna ESPO, classifica, bilancio → assegna nuove missioni → rientro vettori secondo timer. `[F1]`
- [ ] **Vincoli azione/giorno**: 1 sola reclutazione/giorno (§3); missioni assegnate diventano visibili a orario casuale nelle 24 h successive (§9.1). `[F1]`
- [ ] **Grazia UG iniziale** (§0.2): l'UG copre le missioni finché il giocatore non completa la prima (cap 7 giorni). `[F1]`

### 5.2 Governo — Fedeltà Culturale (F1) — §1

- [ ] Scelta cultura + scelta **base sulla Terra** (coordinate) all'onboarding; **cambio cultura libero** in qualsiasi momento. `[F1]`
- [ ] **Moltiplicatore fedeltà LINEARE** (§1, §14): `contributo = base × (1 + fedeltà%/g × giorni_fedeltà)`; **reset a 0** dei giorni di fedeltà al cambio cultura. `[F1]`
- [ ] **Vantaggi culturali** (§1.1) — implementare i 10 effetti unici: Nordamericana (Missioni +25% · Aerei -10% 1/g), Europea (tempo licenze -25%), Cinese (+2 slot hangar permanenti), Africana (+50 R/g per ufficiale), Indiana (1 recluta gratis/g · +2 postazioni missione), Pacifica (manutenzione aerea gratis), Latinoamericana (ESPO ×4), Lunare (-20% spazioplani · +4 postazioni · D-Bronze nativa), Cyber (ESPO ×2), Non Tecnologica (STR combattenti nativi +30%). `[F1]`
- [ ] **Pool nomi reclute** (§1, §3.4): 50% cultura finanziata + 50% altre culture; distribuzioni onomastiche per cultura; i bonus si applicano a tutti i reclutati a prescindere dall'origine. `[F2]`

### 5.3 Bilancio e Prestiti (F1) — §2

- [ ] **Scheda Bilancio** con aggiornamento giornaliero dei flussi (§2.1); saldo **rosso e pulsante** se negativo. `[F1]`
- [ ] **Prestiti** (§2.2): Cultura (×3 contributo, 20 rate/g, 3 slot, 5%) e UG (×10 contributo, 40 rate/g, 2 slot, 20%); rate obbligatorie addebitate al tick. `[F1]`
- [ ] **Stato di default** (§2.3): penale 2%/g sul credito negativo, nessun credito, nessun acquisto fino all'estinzione dei prestiti; a zero debiti un solo prestito alla volta. `[F1]`

### 5.4 Centro Reclute (F2) — §3

- [ ] **Pool giornaliero** con max 1 pilota + max 4 combattenti, parità di genere puramente estetica (solo nomi). `[F2]`
- [ ] **Opzioni di reclutamento** a prezzo fisso (§3.1: 1 pilota 100 R … pilota+4 combattenti 500 R). `[F2]`
- [ ] **Generazione statistiche Pilota** (§3.2): ESPO/STR/STRS via `1%×rand(0,10)+1%×rand(0,5)` (max 15%), arrotondate alla mezza unità; visualizzazione a stelle/quadrato rosso. `[F2]`
- [ ] **Generazione statistiche Combattente** (§3.3): VIT=100, STR/DIF=50–100, MOV=5–20, SPA=0–100, TABI=somma. `[F2]`

### 5.5 Caserma (F2) — §4

- [ ] **Capacità e upgrade** 10→100 posti con costi a scaglione (§4.1). `[F2]`
- [ ] **Licenze pilota** A/B/C/D/E × Bronze/Silver/Gold/Platinum con costo e durata (§4.2); **pilota in addestramento non utilizzabile**; applicare bonus Europea (-25% tempo) e Lunare (D-Bronze nativa). `[F2]`
- [ ] **Addestramento statistiche pilota** (§4.3): 1.000 R, 1 g, +1% a una stat scelta, cap 25%; stelle/quadrati caserma e relativo stipendio. `[F2]`
- [ ] **Addestramento combattenti** (§4.4): 250 R, 1 g, +1 punto; limiti STR/DIF/SPA 200, MOV 25; VIT +1/g gratis in caserma fino a 120; **VIT ≤ 0 → eliminato**. `[F2]`
- [ ] **Stipendio combattente** (§4.5): `√TABI ÷ 5 × moltiplicatore esperienza`, scaglioni esperienza per numero missioni. `[F2]`

### 5.6 Ospedale (F2) — §5

- [ ] **Capacità e upgrade** 2→25 posti (§5.1); selezione giornaliera dei feriti da curare. `[F2]`
- [ ] **Formula di cura** (§5.2): `VIT/g = 20 + rand(-5,+5)`, max 100. `[F2]`

### 5.7 Magazzino (F2) — §6

- [ ] **Equipaggiamento combattenti** (§6.1): 9 livelli Bronze/Silver/Gold con effetti su STR/DIF/MOV/SPA; gestione inventario e **consumo 30% al rientro** (da ricomprare). `[F2]`
- [ ] **Missili** (§6.2): fino a 4 per vettore da caccia; livelli terrestri (STR) e spaziali (STRS); **azzerati al rientro**. `[F2]`

### 5.8 Hangar (F2) — §7

- [ ] **Slot 3→12** con costi e **prerequisiti di sblocco** (es. slot 6 richiede 1 aereo da caccia, slot 9 un aereo spaziale, slot 12 un trasporto civile); applicare bonus Cinese (+2 slot permanenti). `[F2]`

### 5.9 Vettori (F3) — §8

- [ ] **Acquisto/gestione vettori** di tutte le categorie con costo, manutenzione, requisiti licenza (§8.1–8.6); sconto Lunare (-20% spazioplani), manutenzione aerea gratis Pacifica, sconto aerei Nordamericana. `[F3]`
- [ ] **Assegnazione pilota↔vettore** (§8, §14): un pilota pilota qualunque vettore per cui ha licenza ma **uno solo alla volta**; impegnato e non riassegnabile mentre in volo. `[F3]`
- [ ] **Tempo di volo terrestre** (§8): `t_andata = distanza(base, bersaglio) / velocità`, coordinate bersaglio casuali sulla terraferma; si somma al countdown allarme. `[F3]`
- [ ] **Trasferimento Terra–Luna fisso** per teatri lunari (§8.5) — immobilizza il pilota per più giorni. `[F4]`
- [ ] **Aeroplani da esplorazione → ESPO/giorno** (§8.1): `ESPO_effettivo = ESPO_vettore × (1 + ESPO%_pilota)` solo se in volo con pilota assegnato. `[F3]`

### 5.10 Missioni — assegnazione, allarme, tipi (F3/F4) — §9.1–9.3

- [ ] **Generazione e assegnazione** (§9.1): `Missioni_disponibili = giocatori_attivi × 4`; `MissioniGiocatore = 1 + int(disp × ESPO_g / ESPO_tot)`, cap 11; resto a chi è a zero con resto più alto, poi casuale. `[F4]`
- [ ] **Giocatore attivo** = login ≤ 48 h; oltre → **inattivo, rimosso**, missioni pendenti all'UG (§9.1, §9.8). `[F4]`
- [ ] **Sistema di allarme** (§9.2): Verde (7 g, trasferibile ad amica per 25%), Giallo (pubblico dominio 24 h, ricompensa 90%), Rosso (al giorno 12, UG risolve dopo 48 h, ricompensa 50%). `[F4]`
- [ ] **Tipi di missione e date di sblocco** (§9.3): Terrestre (dal 1 lug), Intercettazione Terrestre (dal 15 ago, caccia), Intercettazione Lunare (dal 1 ott, spazio-caccia), Lunare (dal 1 nov, spazio-missione), UG (eventi), Evacuazione (spazioplani civili). `[F4]`

### 5.11 Modello del nemico e scaling (F4) — §9.4

- [ ] **Curva `E(t)`**: Fase A (0–60) lineare `100 + 4t`; Fase B (≥60) composto giornaliero `×1,0371/g` (equivalente a ×1,2 ogni 5 g), continua in t=60. `[F4]`
- [ ] **Potenza nemico Pn** per piano (§9.4): sbarco terrestre `N·E·k_sbarco`, intercettazione aerea `E·k_int`, intercettazione lunare `E·k_int·k_luna`, sbarco lunare `N·E·k_sbarco·k_luna`. `[F4]`
- [ ] **Coefficienti** `k_sbarco=1.0, k_int=1.0, k_luna=1.5` come default (parametrizzabili per il pass Monte Carlo §7). `[F4]`

### 5.12 Risoluzione del combattimento (F3) — §9.5–9.7

- [ ] **Piano A — Intercettazione** (§9.5): `Pg = (Attacco + Σmissili) × (1 + STR%|STRS%) × (1 + 0.1·Velocità)`. `[F3/F4]`
- [ ] **Piano B — Sbarco** (§9.5): `Pg = Σ TABI_efficace` dei combattenti schierati (con armi/armatura terrestre o spaziale). `[F3]`
- [ ] **Esito** (§9.5): fattore casuale indipendente `×rand(0.75,1.25)` su Pg e Pn; `Pg' ≥ Pn'` → riuscita. `[F3]`
- [ ] **Perdite e danni** (§9.6): vittoria schiacciante (≥2×) quasi nulle; vittoria di misura `danno = Pn'×0.5` ripartito **inversamente alla DIF**; sconfitta → danno massimo. `[F3]`
- [ ] **Distruzione vettore + morte pilota** in caso di sconfitta (§9.6) — perdita strutturale; feriti in ospedale o +1 VIT/g in caserma; consumo equip 30% e missili azzerati una sola volta al rientro. `[F3]`
- [ ] **Ricompense** (§9.7): `Pn × molt_tipo × molt_allarme` (Terrestre ×1, Intercettazione ×1.2, Lunare ×1.5, UG variabile; allarme Verde 100% / Giallo 90% / Rosso 50% / trasferita 25%-75%). `[F3/F4]`

### 5.13 Missioni speciali e teatri avanzati (F4) — §9.8–9.11

- [ ] **Missioni UG** (§9.8): eventi multi-vettore con scadenza e ricompensa elevata, legate alla lore ("Oggetto Sigma"); coordinate via Thread Operazione UG (§13). `[F5]`
- [ ] **Evacuazione civili** (§9.9): spazioplani civili (capacità H); `ricompensa = civili_salvati × tariffa_per_H`. `[F4]`
- [ ] **Sortie multi-missione** (§9.11): catena di tappe con un solo rientro; pool unico di 4 missili; VIT accumulata senza cura intermedia; consumo 30% una sola volta; vincolo lunghezza catena (es. max 4 tappe). `[F4]`

### 5.14 Interfaccia di caricamento missione — 5 schermate (F3) — §9.10

- [ ] **Plancia Missioni**: mappa Terra/Luna + lista missioni con tipo, allarme, countdown, **Pn come banda ±25%**, ricompensa stimata, vettore richiesto. `[F3]`
- [ ] **Selezione vettore**: filtro per licenza/tipo; vettori liberi + vettori in volo a cui accodare (ETA e tappe in coda). `[F3]`
- [ ] **Loadout**: sbarco (griglia postazioni 8/12/16/20, drag combattenti, arma+armatura, Σ TABI in tempo reale) / intercettazione (1 pilota + ≤4 missili, calcolo Pg); **simulatore** con barra di probabilità ±25%, esito atteso, perdite stimate. `[F3]`
- [ ] **Sortie planner**: rotta su mappa, somma tempi ridotti, degrado progressivo (VIT, missili). `[F4]`
- [ ] **Conferma & pannello In Volo**: timer + ETA + coda; al rientro log tappa per tappa, perdite, feriti in ospedale, consumo e missili; notifiche nel canale Delpy. `[F3]`

### 5.15 Co-finanziamento UG (F5) — §10

- [ ] **Formula**: `Co-finanziamento UG/g = 100 R × missioni completate nelle ultime 48 h`; integrata nel flusso giornaliero (§2.1). `[F5]`

### 5.16 Classifica, Ciclo dei 40 Giorni, Endgame (F5) — §11

- [ ] **Punteggio** = numero missioni completate; **spareggio** = ESPO totale lifetime. `[F5]`
- [ ] **Ciclo 40 giorni**: missione speciale **Trasporto Coloni** (vale 25 missioni, vinta dalla metà più attiva) + **Taglio UG** del 25% peggiore per missioni. `[F5]`
- [ ] **Imbuto di consolidamento endgame** (§11.1): 3 cicli individuali al 25% (256→192→144→108), poi alla soglia ≤112 fase-alleanza con Taglio per alleanza (elimina la peggiore, 1 su 4) fino alle **3 alleanze superstiti** (~81 giocatori); fusione forzata sotto soglia; missione finale → vittoria. `[F5]`

### 5.17 Alleanze (F5) — §12

- [ ] **Edificio Alleanza** fino a 28 membri; **Capoalleanza** obbligatoriamente attivo. `[F5]`
- [ ] **Tesoreria comune** controllata dal Capoalleanza con delega a max 4 **Colonnelli**; acquisti dai fondi comuni previa autorizzazione. `[F5]`
- [ ] **Missioni comuni**: missione trasferita all'alleanza entra in pool comune (chiunque la svolge); ricompensa 25% a chi la svolge / resto al trasferente. `[F5]`
- [ ] **Pooling delle forze** rilevante in Fase B per reggere lo scaling nemico. `[F5]`

### 5.18 Sistema di chat (F5) — §13

- [ ] **Async-first**: messaggi persistenti, notifiche, badge non-letti. `[F5]`
- [ ] **Canali**: UG-Net globale (slow-mode, rate-limit), 10 canali Cultura, canale Alleanza privato (≤28, pin, azioni inline), DM 1:1, Thread Operazione UG temporanei, **canale Delpy di sistema** (feed notifiche narrate). `[F5]`
- [ ] **Funzioni trasversali**: azioni di gioco inline (offerta trasferimento missione cliccabile, condivisione battle report), **anti-abuso** (rate-limit, mute/block, report, filtro spam, contrasto alt-account), traduzione automatica inline su canali globale/cultura, patti formali tra alleanze registrati dal sistema. `[F5]`

### 5.19 Monetizzazione e Shop (F6) — doc Shop

- [ ] **Sezione Digitale**: 11 Pacchetti Plus (10 cultura + 1 Core/IA) a 5,00 €; contenuto (2 piloti + 8 combattenti + 1 vettore con skin / pacchetto Core 10 unità miste + vettore skin Delpy). `[F6]`
- [ ] **Regola Anti-P2W (Soluzione C)**: max **1 pacchetto per ciclo di 40 giorni**, max 1/giorno; unità in **Pool di Riserva Premium** da cui si attinge ai normali turni di reclutamento in R (non bypassano il limite giornaliero). `[F6]`
- [ ] **Ticket Server Pro** 10,00 €: server d'élite a 256 agenzie; al Giorno 1 tutti scelgono fazione e ricevono il Pacchetto Plus **gratis** (equità competitiva). `[F6]`
- [ ] **Sezione Campioni** (accesso ai soli vincitori certificati, max 12 mesi): 10 Anelli dei Leader (MVP per cultura), Anello "AI" Supremo (Generalissimo), Giacca Pilota "Veteran"; sblocco automatico **badge olografico** su UG-Net. `[F6]`
- [ ] **Sezione Fisica per tutti**: Anelli di Fazione standard (49–69 €), abbigliamento UG-Net, logistica da scrivania. `[F6]`
- [ ] **Server Campioni** (1×/anno, su invito, ticket 100 €): velocità ×4, campagna ~40 giorni, Taglio UG ogni 10 giorni; unica fonte degli 11 anelli numerati con anno inciso. `[F6]`
- [ ] **Devoluzione 10% Agenda 2030**: calcolo automatico sul lordo shop (digitale/fisico/ticket) + **tracciabilità trasparente** dell'impatto su ogni transazione. `[F6]`

### 5.20 Narrativa & integrazione lore (trasversale)

- [ ] **Persona Delpy** per il canale di sistema: tono e testi delle notifiche (missione assegnata, rientro vettore, saldo rosso/pre-default, allarme che sale, pre-Taglio UG, sblocco nuovi tipi missione) (§13). `[F4]`
- [ ] **Aggancio missioni UG alla lore** ("Oggetto Sigma", Operazione Specchio, difesa di Delta) con testi dedicati (§9.8). `[F5]`
- [ ] **Collegamento col sito vetrina esistente**: voce *Game* (`game.html`) punta all'app; riuso schede Culture/Personaggi di `story/` per onboarding e canali Cultura. `[F3]`

---

## 6. Bilanciamento e simulazione (F7) — §9.4, §11.1, §14

- [ ] **Motore di simulazione Monte Carlo** (200.000 prove/scenario, ±25% su entrambe le Potenze) per validare i coefficienti di combattimento. `[F7]`
- [ ] **Confermare il fork `k_luna`** (1.5 vs 2.0, o coefficienti separati int/sbarco) — decidere se lo sbarco lunare è solo-difficile o esclusivo delle alleanze (§14, **questione aperta**). `[F7]`
- [ ] **Validare la curva di Fase B** e la transizione continua a t=60; verificare la banda di reddito lineare ~450–2.100 R/g sull'arco vita server. `[F7]`
- [ ] **Validare l'imbuto endgame** (256→…→3 alleanze) su una simulazione di server completo. `[F7]`

---

## 7. QA, sicurezza, performance (F7)

- [ ] **Test unitari** su tutte le formule (statistiche, stipendi, cura, Pn, Pg, ricompense, fedeltà, co-finanziamento).
- [ ] **Test di integrazione del tick** (idempotenza, ripartenza, ordine flussi).
- [ ] **Test del ciclo competitivo completo** (40 giorni × più cicli) in ambiente accelerato.
- [ ] **Anti-abuso**: alt-account, exploit trasferimento missioni, accumulo fedeltà, rate-limit chat (§13).
- [ ] **Performance**: tick su 256 agenzie attive + assegnazione missioni di massa entro finestra accettabile.
- [ ] **Carico realtime** chat/notifiche.

---

## 8. Questioni aperte da risolvere prima/durante lo sviluppo (§14)

1. **Modello server/shard e monetizzazione**: confermare se le 256 agenzie sono per shard e come si istanziano F2P/Pro/Campioni. *Vincolo: nessuna meccanica pay-to-win* (ladder competitiva a vita finita). → blocca F0 e F6.
2. **Valore di `k_luna`** e fascia degli sbarchi lunari (1.5 vs 2.0 vs coefficienti separati) → blocca la calibrazione finale F7.
3. **Lunghezza massima catena sortie** (valore numerico definitivo o "autonomia" per progetto, §9.11).
4. **Tariffa per H** dell'evacuazione civili e parametri delle missioni UG/Trasporto Coloni (valori non esplicitati nel GDD).

> Le altre voci di §14 risultano **risolte** nel GDD v3 e sono già recepite nei task sopra
> (fedeltà lineare con reset, morte pilota/distruzione vettore, assegnazione pilota-vettore,
> tempo di volo, ESPO% pilota, attivo/inattivo, formula assegnazione missioni, alleanze/tesoreria,
> imbuto endgame, genere estetico, coefficienti di combattimento).

---

## 9. Ordine di lavoro consigliato (sintesi)

1. **F0** Fondamenta + decisione modello server.
2. **F1** Tick + economia + governo (è il cuore: senza tick coerente niente regge).
3. **F2** Personale ed edifici (reclute → caserma/ospedale/magazzino/hangar).
4. **F3** Vettori + missioni terrestri + risoluzione + UI 5 schermate (primo loop giocabile end-to-end).
5. **F4** Scaling `E(t)` + teatri aerei/lunari + evacuazione + sortie.
6. **F5** Multiplayer: classifica, co-finanziamento, ciclo 40g, alleanze, chat, missioni UG, endgame.
7. **F6** Monetizzazione e shop.
8. **F7** Bilanciamento Monte Carlo, anti-abuso, performance, QA finale.
