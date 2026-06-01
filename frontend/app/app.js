/* SX2128 — Console Agenzia (SPA vanilla)
   F5: Classifica, Alleanze, Chat, Ciclo 40gg */

const S = {
  token: localStorage.getItem("sx_token") || null,
  serverId: localStorage.getItem("sx_server") || null,
  cultures: [],
  vehicles_catalog: [],
  recruit_opts: {},
  log: [],
  tab: "overview",
  data: {
    ag: null, pilots: [], fighters: [], vehicles: [], missions: [],
    classifica: [], alliance: null, chat_delpy: [], chat_ugnet: [],
  },
  _launchMid: null,
  _launchIsIntercept: false,
};

const api = () => document.getElementById("apiBase").value.replace(/\/$/, "");
const $ = (id) => document.getElementById(id);
const app = () => document.getElementById("app");

function logLine(msg) {
  S.log.unshift(`[${new Date().toLocaleTimeString()}] ${msg}`);
  S.log = S.log.slice(0, 80);
  const el = document.getElementById("log");
  if (el) el.textContent = S.log.join("\n");
}

async function req(path, { method = "GET", body, form } = {}) {
  const headers = {};
  if (S.token) headers["Authorization"] = `Bearer ${S.token}`;
  let payload;
  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    payload = new URLSearchParams(form).toString();
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(api() + path, { method, headers, body: payload });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ? JSON.stringify(data.detail) : res.status);
  return data;
}

/* ────────────────────────── Auth ────────────────────────── */
function viewAuth() {
  app().innerHTML = `
  <section class="card">
    <h2>Accesso Generale</h2>
    <div class="row">
      <div style="flex:1"><label>Email</label><input id="email" value="generale@ug.net" /></div>
      <div style="flex:1"><label>Password</label><input id="pw" type="password" value="secret1" /></div>
    </div>
    <div class="row" style="margin-top:14px">
      <button onclick="doAuth('register')">Registra</button>
      <button class="ghost" onclick="doAuth('login')">Login</button>
    </div>
    <div id="authErr" class="err"></div>
  </section>`;
}

async function doAuth(kind) {
  $("authErr").textContent = "";
  try {
    let data;
    if (kind === "register") {
      data = await req("/api/auth/register", { method: "POST", body: { email: $("email").value, password: $("pw").value } });
    } else {
      data = await req("/api/auth/login", { method: "POST", form: { username: $("email").value, password: $("pw").value } });
    }
    S.token = data.access_token;
    localStorage.setItem("sx_token", S.token);
    logLine("autenticato");
    await boot();
  } catch (e) { $("authErr").textContent = "Errore: " + e.message; }
}

/* ────────────────────────── Setup ────────────────────────── */
function viewSetup() {
  const opts = S.cultures.map(c => `<option value="${c.id}">${c.nome} — ${c.base_r_giorno} R/g · +${c.fedelta_pct_giorno}%/g</option>`).join("");
  app().innerHTML = `
  <section class="card">
    <h2>Crea / Seleziona Server</h2>
    <div class="row">
      <input id="srvName" placeholder="Nome server" value="Fronte Delta" style="flex:2" />
      <select id="srvType" style="flex:1">
        <option value="f2p">F2P</option><option value="pro">Pro</option><option value="campioni">Campioni (x4)</option>
      </select>
      <button onclick="createServer()">Crea server</button>
    </div>
    <label>oppure inserisci ID server esistente</label>
    <div class="row"><input id="srvId" placeholder="ID server" style="flex:1"/><button class="ghost" onclick="useServer()">Usa</button></div>
  </section>
  <section class="card">
    <h2>Fonda la tua Agenzia</h2>
    <div class="row">
      <div style="flex:2"><label>Nome agenzia</label><input id="agName" value="Difensori di Roma"/></div>
      <div style="flex:2"><label>Cultura (§1.1)</label><select id="agCulture">${opts}</select></div>
    </div>
    <div class="row" style="margin-top:8px">
      <div style="flex:1"><label>Base lat</label><input id="lat" value="41.9"/></div>
      <div style="flex:1"><label>Base lon</label><input id="lon" value="12.5"/></div>
      <button class="mag" style="align-self:flex-end" onclick="createAgency()">Fonda agenzia</button>
    </div>
    <div id="setupErr" class="err"></div>
  </section>
  <section class="card"><h2>Log · Delpy</h2><div id="log" class="log">${S.log.join("\n")}</div></section>`;
}

async function createServer() {
  try {
    const d = await req("/api/admin/server", { method: "POST", body: { name: $("srvName").value, server_type: $("srvType").value } });
    S.serverId = d.id; localStorage.setItem("sx_server", d.id);
    logLine(`server #${d.id} "${d.name}" creato`);
    await boot();
  } catch (e) { $("setupErr").textContent = e.message; }
}
function useServer() {
  S.serverId = $("srvId").value; localStorage.setItem("sx_server", S.serverId); boot();
}
async function createAgency() {
  $("setupErr").textContent = "";
  try {
    await req("/api/agency", { method: "POST", body: {
      server_id: Number(S.serverId), name: $("agName").value, culture: $("agCulture").value,
      base_lat: Number($("lat").value), base_lon: Number($("lon").value) } });
    logLine("agenzia fondata · capitale iniziale 2.000 R");
    await boot();
  } catch (e) { $("setupErr").textContent = e.message; }
}

/* ────────────────────────── Dashboard ────────────────────────── */
function stat(k, v, cls = "") {
  return `<div class="stat"><div class="k">${k}</div><div class="v ${cls}">${v}</div></div>`;
}

function vitBar(vit) {
  const pct = Math.min(100, vit);
  const cls = pct >= 80 ? "ok" : pct >= 40 ? "warn" : "bad";
  return `${vit}<span class="vit-bar"><span class="vit-fill" style="width:${pct}%;background:var(--${cls})"></span></span>`;
}

function statusPill(s) {
  const cls = s === "barracks" ? "" : s === "training" ? "warn" : s === "hospital" ? "warn" : s === "in_flight" ? "ok" : "bad";
  const labels = { barracks: "Caserma", training: "In addestramento", hospital: "Ospedale", in_flight: "In volo", eliminated: "Elim." };
  return `<span class="pill ${cls}">${labels[s] || s}</span>`;
}

function licenseBadges(lic) {
  const clean = Object.entries(lic).filter(([k]) => !k.startsWith("__"));
  if (!clean.length) return '<span class="muted">nessuna</span>';
  return clean.map(([t, tier]) => `<span class="pill">${t.toUpperCase()}-${tier}</span>`).join(" ");
}

function equipBadge(equip, slot) {
  const e = equip[slot];
  if (!e) return `<span class="equip-slot">${slot}</span>`;
  return `<span class="equip-slot filled">${e.livello}</span>`;
}

/* ── tab rendering ── */

function renderOverview(ag) {
  const recruitOpts = Object.entries(S.recruit_opts || {}).map(([k, v]) =>
    `<option value="${k}">${k.replaceAll("_", " ")} — ${v.cost} R</option>`).join("");
  return `
  <section class="card">
    <h2>${ag.name} <span class="pill">${ag.culture}</span> ${ag.in_default ? '<span class="pill bad">DEFAULT</span>' : ''}</h2>
    <div class="grid">
      ${stat("Saldo (R)", Math.round(ag.balance), ag.balance < 0 ? "bad" : "ok")}
      ${stat("Fedeltà (gg)", ag.loyalty_days)}
      ${stat("ESPO oggi", Math.round(ag.espo_today))}
      ${stat("ESPO totale", Math.round(ag.espo_total))}
      ${stat("Missioni", ag.missions_completed)}
      ${stat("Caserma", ag.barracks_capacity + " posti")}
      ${stat("Ospedale", ag.hospital_capacity + " letti")}
      ${stat("Hangar", ag.hangar_slots + " slot")}
    </div>
  </section>
  <section class="card">
    <h2>Centro Reclute <span class="muted" style="font-size:12px">(§3 · 1/giorno)</span></h2>
    <div class="row">
      <select id="recruitOpt" style="flex:2">${recruitOpts}</select>
      <button onclick="doRecruit()">Recluta</button>
      <button class="ghost" onclick="doTick()">⏭ Avanza giorno (tick)</button>
    </div>
    <div id="dashErr" class="err"></div>
  </section>`;
}

function renderBuildings(ag) {
  return `
  <section class="card">
    <h2>Edifici — Upgrade (§4.1, §5.1, §7)</h2>
    <div class="grid">
      <div class="stat">
        <div class="k">Caserma</div>
        <div class="v">${ag.barracks_capacity} / 100</div>
        <button class="sm" style="margin-top:8px" onclick="upgradeBuilding('barracks')">Upgrade</button>
        <div id="err-barracks" class="section-err"></div>
      </div>
      <div class="stat">
        <div class="k">Ospedale</div>
        <div class="v">${ag.hospital_capacity} / 25</div>
        <button class="sm" style="margin-top:8px" onclick="upgradeBuilding('hospital')">Upgrade</button>
        <div id="err-hospital" class="section-err"></div>
      </div>
      <div class="stat">
        <div class="k">Hangar</div>
        <div class="v">${ag.hangar_slots} / 12</div>
        <button class="sm" style="margin-top:8px" onclick="upgradeBuilding('hangar')">Upgrade</button>
        <div id="err-hangar" class="section-err"></div>
      </div>
    </div>
  </section>`;
}

function renderPilots(pilots) {
  if (!pilots.length) return '<section class="card"><h2>Piloti</h2><p class="muted">Nessun pilota. Recluta nella scheda Panoramica.</p></section>';
  const rows = pilots.map(p => `
    <tr>
      <td><b>${p.name}</b><br><small class="muted">${p.origin_culture}</small></td>
      <td>${statusPill(p.status)}</td>
      <td>ESPO ${p.espo_pct.toFixed(1)}% / STR ${p.str_pct.toFixed(1)}% / STRS ${p.strs_pct.toFixed(1)}%</td>
      <td>${licenseBadges(p.licenses)}</td>
      <td>
        <div class="btns">
          <button class="sm ghost" onclick="trainLicenseDialog(${p.id})">Licenza</button>
          <button class="sm ghost" onclick="trainStatDialog(${p.id})">Stat +1%</button>
        </div>
        ${p.training_info ? `<small class="warn">▷ ${p.training_info} (gg ${p.training_until_day})</small>` : ""}
      </td>
    </tr>`).join("");
  return `
  <section class="card">
    <h2>Piloti (${pilots.length})</h2>
    <div id="pilot-err" class="err"></div>
    <table>
      <thead><tr><th>Nome</th><th>Stato</th><th>Statistiche</th><th>Licenze</th><th>Azioni</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </section>
  <div id="pilot-dialog" style="display:none" class="card">
    <h3 id="dialog-title">Addestramento</h3>
    <div id="dialog-content"></div>
    <button class="sm bad" style="margin-top:10px" onclick="closeDialog()">Chiudi</button>
  </div>`;
}

function renderFighters(fighters) {
  if (!fighters.length) return '<section class="card"><h2>Combattenti</h2><p class="muted">Nessun combattente. Recluta nella scheda Panoramica.</p></section>';
  const rows = fighters.map(f => `
    <tr>
      <td><b>${f.name}</b><br><small class="muted">${f.origin_culture}</small></td>
      <td>${statusPill(f.status)}</td>
      <td>VIT ${vitBar(f.vit)}</td>
      <td>STR ${f.str} / DIF ${f.dif} / MOV ${f.mov} / SPA ${f.spa}<br><small class="muted">TABI ${f.tabi}</small></td>
      <td>
        ${equipBadge(f.equipment, "weapon")}
        ${equipBadge(f.equipment, "armor_terra")}
        ${equipBadge(f.equipment, "armor_spazio")}
      </td>
      <td>
        <div class="btns">
          ${f.status === "barracks" ? `<button class="sm ghost" onclick="trainFighterDialog(${f.id})">Allena</button>` : ""}
          ${f.status === "barracks" && f.vit < 100 ? `<button class="sm warn" onclick="hospitalize(${f.id})">Ospedale</button>` : ""}
          ${f.status === "hospital" ? `<button class="sm ghost" onclick="discharge(${f.id})">Dimetti</button>` : ""}
          ${f.status === "barracks" ? `<button class="sm ghost" onclick="equipDialog(${f.id})">Equipaggia</button>` : ""}
        </div>
        ${f.training_stat ? `<small class="warn">▷ ${f.training_stat} (gg ${f.training_until_day})</small>` : ""}
      </td>
    </tr>`).join("");
  return `
  <section class="card">
    <h2>Combattenti (${fighters.length})</h2>
    <div id="fighter-err" class="err"></div>
    <table>
      <thead><tr><th>Nome</th><th>Stato</th><th>VIT</th><th>Statistiche</th><th>Equip.</th><th>Azioni</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </section>
  <div id="fighter-dialog" style="display:none" class="card">
    <h3 id="fdialog-title">Azione</h3>
    <div id="fdialog-content"></div>
    <button class="sm bad" style="margin-top:10px" onclick="closeFDialog()">Chiudi</button>
  </div>`;
}

function renderVehicles(vehicles, pilots) {
  const pilotMap = Object.fromEntries(pilots.map(p => [p.id, p.name]));
  const vcats = [...new Set(S.vehicles_catalog.map(v => v.vclass))];
  const catOpts = vcats.map(c => `<optgroup label="${c}">${
    S.vehicles_catalog.filter(v => v.vclass === c).map(v => `<option value="${v.project}">${v.project} — ${v.cost}R</option>`).join("")
  }</optgroup>`).join("");

  const rows = vehicles.map(v => {
    const pilot = v.pilot_id ? pilotMap[v.pilot_id] : null;
    const mis = `T:${v.missiles.terra.count||0}/${v.missiles.terra.key||"—"} S:${v.missiles.spazio.count||0}/${v.missiles.spazio.key||"—"}`;
    return `
    <tr>
      <td><b>${v.project}</b><br><small class="muted">${v.vclass}</small></td>
      <td>${statusPill(v.status)}${v.return_day != null ? `<br><small>ETA gg ${v.return_day.toFixed(1)}</small>` : ""}</td>
      <td>${pilot ? `<span class="pill ok">${pilot}</span>` : '<span class="muted">—</span>'}</td>
      <td><small>${mis}</small></td>
      <td>
        <div class="btns">
          <button class="sm ghost" onclick="assignPilotDialog(${v.id})">Pilota</button>
          ${v.vclass==="fighter"||v.vclass==="space_fighter" ? `<button class="sm ghost" onclick="missilesDialog(${v.id})">Missili</button>` : ""}
        </div>
      </td>
    </tr>`;
  }).join("");

  return `
  <section class="card">
    <h2>Vettori (${vehicles.length} / ${S.data.ag?.hangar_slots||0} slot)</h2>
    <div class="row" style="margin-bottom:12px">
      <select id="buyProject" style="flex:3">${catOpts}</select>
      <button onclick="buyVehicle()">Acquista vettore</button>
    </div>
    <div id="vehicle-err" class="err"></div>
    ${vehicles.length ? `
    <table>
      <thead><tr><th>Vettore</th><th>Stato</th><th>Pilota</th><th>Missili</th><th>Azioni</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>` : '<p class="muted">Hangar vuoto.</p>'}
  </section>
  <div id="vehicle-dialog" style="display:none" class="card">
    <h3 id="vdialog-title">Azione vettore</h3>
    <div id="vdialog-content"></div>
    <button class="sm bad" style="margin-top:10px" onclick="closeVDialog()">Chiudi</button>
  </div>`;
}

/* ── missions tab ── */

function _alarmBadge(alarm) {
  const cls = { verde: "ok", giallo: "warn", arancione: "warn", rosso: "bad" };
  const icons = { verde: "●", giallo: "⚠", rosso: "🔴" };
  return `<span class="pill ${cls[alarm]||""}">${icons[alarm]||""} ${alarm.toUpperCase()}</span>`;
}

function _mtypeLabel(t) {
  return {
    terrestre: "Terrestre", lunare: "Lunare",
    intercept_terra: "Intercett. Terra", intercept_luna: "Intercett. Luna",
    evacuazione: "Evacuazione", ug: "UG ★",
  }[t] || t;
}

function _missionDetail(m) {
  if (m.mission_type === "evacuazione") {
    return `${m.civili_da_salvare?.toLocaleString()} civili`;
  }
  return `Pn ${m.pn}`;
}

function renderMissions(missions, vehicles, fighters) {
  const assigned = missions.filter(m => m.status === "assigned");
  const inflight = missions.filter(m => m.status === "in_progress");
  const done = missions.filter(m => m.status === "completed" || m.status === "failed");

  // Group in-flight by vehicle (chains share the same return_day)
  const inflightByVehicle = {};
  inflight.forEach(m => {
    const key = m.vehicle_id || m.id;
    if (!inflightByVehicle[key]) inflightByVehicle[key] = [];
    inflightByVehicle[key].push(m);
  });

  const hasAlliance = !!S.data.ag?.alliance_id;
  const assignedRows = assigned.map(m => `
    <tr>
      <td>${_alarmBadge(m.alarm)}<br><small>${_mtypeLabel(m.mission_type)}</small></td>
      <td>${m.target_lat?.toFixed(1)}°, ${m.target_lon?.toFixed(1)}°</td>
      <td>${_missionDetail(m)}</td>
      <td>~${m.reward_estimate} R</td>
      <td>gg ${m.deadline_day}</td>
      <td>
        <div class="btns">
          <button class="sm" onclick="launchDialog(${m.id},'${m.mission_type}')">Lancia</button>
          ${hasAlliance && m.alarm === "verde" ? `<button class="sm ghost" onclick="doTransferMission(${m.id})">→Alleanza</button>` : ""}
        </div>
        ${m.chain_leg > 0 ? `<small class="muted">Tappa ${m.chain_leg}</small>` : ""}
      </td>
    </tr>`).join("");

  const inflightRows = Object.values(inflightByVehicle).map(legs => {
    legs.sort((a, b) => a.chain_leg - b.chain_leg);
    const first = legs[0];
    const isChain = legs.length > 1;
    const eta = first.sortie_return_day != null ? `ETA gg ${first.sortie_return_day.toFixed(1)}` : "—";
    return `
    <tr>
      <td>${_alarmBadge(first.alarm)}<br><small>${legs.map(l => _mtypeLabel(l.mission_type)).join(" → ")}</small></td>
      <td><span class="pill ok">In volo</span>${isChain ? ` <span class="pill">${legs.length} tappe</span>` : ""}</td>
      <td>${eta}</td>
      <td>~${legs.reduce((s, l) => s + l.reward_estimate, 0).toFixed(0)} R</td>
      <td>${first.fighters?.length ? first.fighters.length + " comb." : "—"}</td>
    </tr>`;
  }).join("");

  const doneRows = done.slice(0, 10).map(m => {
    const ok = m.status === "completed";
    const res = m.resolution;
    let detail = "";
    if (res) {
      if (res.civili_salvati != null) {
        detail = `${res.civili_salvati.toLocaleString()} civili salvati · +${res.ricompensa} R`;
      } else {
        detail = `Pg ${res.pg} vs Pn ${res.pn} [eff: ${res.pg_eff} vs ${res.pn_eff}]${res.ricompensa ? " · +" + res.ricompensa + " R" : ""}`;
      }
    }
    return `
    <tr>
      <td>${_alarmBadge(m.alarm)}<br><small>${_mtypeLabel(m.mission_type)}</small></td>
      <td><span class="pill ${ok?"ok":"bad"}">${ok?"Successo":"Fallita"}</span></td>
      <td>gg ${m.assigned_day}</td>
      <td colspan="2"><small class="muted">${detail}</small></td>
    </tr>`;
  }).join("");

  return `
  <section class="card">
    <h2>Missioni Assegnate (${assigned.length})</h2>
    <div id="mission-err" class="err"></div>
    ${assigned.length ? `
    <table>
      <thead><tr><th>Tipo</th><th>Coord.</th><th>Pn</th><th>Premio</th><th>Scad.</th><th></th></tr></thead>
      <tbody>${assignedRows}</tbody>
    </table>` : '<p class="muted">Nessuna missione assegnata. Avanza il giorno con il tick.</p>'}
  </section>
  ${inflight.length ? `
  <section class="card">
    <h2>Sortie in Volo (${inflight.length})</h2>
    <table>
      <thead><tr><th>Tipo</th><th>Stato</th><th>Pn</th><th>Premio est.</th><th>Carichi</th></tr></thead>
      <tbody>${inflightRows}</tbody>
    </table>
  </section>` : ""}
  ${done.length ? `
  <section class="card">
    <h2>Storico Missioni</h2>
    <table>
      <thead><tr><th>Tipo</th><th>Esito</th><th>Giorno</th><th colspan="2">Dettaglio combattimento</th></tr></thead>
      <tbody>${doneRows}</tbody>
    </table>
  </section>` : ""}
  <div id="launch-dialog" style="display:none" class="card">
    <h3>Lancia Missione</h3>
    <div id="launch-content"></div>
    <div class="row" style="margin-top:10px">
      <button onclick="doLaunchMission()">Lancia</button>
      <button class="ghost" onclick="closeLDialog()">Annulla</button>
    </div>
    <div id="launch-err" class="err"></div>
    <div id="sim-result" style="margin-top:12px"></div>
  </div>`;
}

/* ── F6: Shop ── */
function renderShop(ag, catalog, pool, transactions) {
  const poolSize = pool.pool_size || 0;
  const poolDetail = pool.pool
    ? Object.entries(pool.pool).map(([k, v]) => `${v}× ${k}`).join(", ")
    : "vuoto";

  const pkgCards = catalog.map(p => {
    const isPlus = p.package_type === "plus";
    const unitDesc = isPlus
      ? `${p.pilots} piloti + ${p.fighters} combattenti${p.vehicle ? " + 1 vettore" : ""}`
      : p.desc;
    const agenda = `Agenda 2030: ${p.agenda_2030_eur}€`;
    const typeTag = isPlus
      ? `<span class="pill">Plus</span>`
      : `<span class="pill warn">${p.package_type === "ticket_pro" ? "Pro" : "Campioni"}</span>`;
    return `
    <div style="border:1px solid var(--border);border-radius:8px;padding:14px;display:flex;flex-direction:column;gap:8px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <b>${p.nome}</b> ${typeTag}
          <br><small class="muted">${unitDesc}</small>
        </div>
        <div style="text-align:right">
          <div style="font-size:18px;font-weight:700">${p.price_eur.toFixed(2)} €</div>
          <small class="muted">${agenda}</small>
        </div>
      </div>
      <button class="sm" onclick="doBuyPackage('${p.key}')">Acquista</button>
    </div>`;
  }).join("");

  const txRows = transactions.slice(0, 10).map(t => `
    <tr>
      <td>${t.package_key}</td>
      <td>${t.price_eur.toFixed(2)} €</td>
      <td class="ok">${t.agenda_2030_eur.toFixed(2)} €</td>
      <td>Ciclo ${t.cycle_at_purchase}</td>
      <td><small class="muted">${new Date(t.created_at).toLocaleDateString()}</small></td>
    </tr>`).join("");

  return `
  <section class="card">
    <h2>Pool di Riserva Premium §5.19</h2>
    <div class="grid" style="margin-bottom:12px">
      ${stat("Unità in pool", poolSize)}
      ${stat("Dettaglio", poolDetail)}
    </div>
    ${poolSize > 0 ? `
    <div class="row" style="flex-wrap:wrap;gap:8px">
      <button class="sm" onclick="doRedeem('pilot')">Riscatta Pilota</button>
      <button class="sm ghost" onclick="doRedeem('fighter')">Riscatta Combattente</button>
      <button class="sm ghost" onclick="doRedeem('vehicle')">Riscatta Vettore</button>
    </div>
    <div id="shop-pool-err" class="err"></div>` : ""}
  </section>
  <section class="card">
    <h2>Catalogo Shop <span class="muted" style="font-size:12px">— anti-P2W: max 1 pacchetto Plus/ciclo, max 1/giorno</span></h2>
    <div id="shop-err" class="err"></div>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;margin-top:10px">
      ${pkgCards}
    </div>
  </section>
  ${transactions.length ? `
  <section class="card">
    <h2>Storico Acquisti — Tracciabilità Agenda 2030</h2>
    <table>
      <thead><tr><th>Pacchetto</th><th>Prezzo</th><th>Agenda 2030 (10%)</th><th>Ciclo</th><th>Data</th></tr></thead>
      <tbody>${txRows}</tbody>
    </table>
  </section>` : ""}`;
}

/* ── F5: Classifica ── */
function renderClassifica(classifica, myAgencyId) {
  if (!classifica.length) return '<section class="card"><h2>Classifica</h2><p class="muted">Nessun dato — avanza il tick.</p></section>';
  const rows = classifica.map(r => {
    const isMe = r.agency_id === myAgencyId;
    const al = r.alliance_id ? `<span class="pill">#${r.alliance_id}</span>` : "";
    const active = r.active ? "" : '<span class="pill bad">inattivo</span>';
    return `<tr${isMe ? ' style="background:var(--surface2)"' : ''}>
      <td><b>#${r.rank}</b></td>
      <td>${r.name}${isMe ? ' <span class="pill ok">tu</span>' : ""}${active}</td>
      <td><span class="pill">${r.culture}</span></td>
      <td><b>${r.missions_completed}</b></td>
      <td>${Math.round(r.espo_total)}</td>
      <td>${Math.round(r.balance)} R</td>
      <td>${al}${r.alliance_role ? `<small class="muted">${r.alliance_role}</small>` : ""}</td>
    </tr>`;
  }).join("");
  return `
  <section class="card">
    <h2>Classifica §11</h2>
    <table>
      <thead><tr><th>Pos.</th><th>Agenzia</th><th>Cultura</th><th>Missioni</th><th>ESPO tot.</th><th>Saldo</th><th>Alleanza</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </section>`;
}

/* ── F5: Alleanze ── */
function renderAlleanze(ag, alliance, alliances) {
  const isInAlliance = !!ag.alliance_id;
  const isCap = ag.alliance_role === "capo";

  let alDetail = "";
  if (isInAlliance && alliance) {
    const membRows = (alliance.members || []).map(m => `
      <tr>
        <td>${m.name}</td>
        <td><span class="pill${m.role==="capo"?" ok":""}">${m.role}</span></td>
        <td>${m.missions_completed}</td>
      </tr>`).join("");
    alDetail = `
    <section class="card">
      <h2>${alliance.name} <span class="muted" style="font-size:12px">id #${alliance.id}</span></h2>
      <div class="grid" style="margin-bottom:12px">
        ${stat("Tesoreria", Math.round(alliance.treasury) + " R")}
        ${stat("Membri", (alliance.members||[]).length + " / 28")}
        ${stat("Ruolo tuo", ag.alliance_role)}
      </div>
      <table>
        <thead><tr><th>Membro</th><th>Ruolo</th><th>Missioni</th></tr></thead>
        <tbody>${membRows}</tbody>
      </table>
      <div class="row" style="margin-top:12px;flex-wrap:wrap;gap:8px">
        ${isCap ? `
          <input id="alDepositAmt" type="number" value="100" style="width:90px"/>
          <button class="sm" onclick="doAllianceDeposit()">Deposita in tesoreria</button>
          <button class="sm ghost" onclick="doAllianceWithdraw()">Preleva</button>
        ` : `
          <input id="alDepositAmt" type="number" value="100" style="width:90px"/>
          <button class="sm" onclick="doAllianceDeposit()">Deposita in tesoreria</button>
        `}
        <button class="sm bad" onclick="doLeaveAlliance()">Lascia alleanza</button>
      </div>
      <div id="al-err" class="err"></div>
    </section>`;
  } else {
    const otherList = (alliances||[]).filter(a => !isInAlliance).map(a =>
      `<tr><td>${a.name}</td><td>${(a.members||[]).length}/28</td>
       <td><button class="sm" onclick="doJoinAlliance(${a.id})">Entra</button></td></tr>`
    ).join("");
    alDetail = `
    <section class="card">
      <h2>Crea Alleanza</h2>
      <div class="row">
        <input id="alName" placeholder="Nome alleanza" style="flex:2"/>
        <button onclick="doCreateAlliance()">Crea</button>
      </div>
      <div id="al-err" class="err"></div>
    </section>
    ${otherList ? `
    <section class="card">
      <h2>Alleanze disponibili</h2>
      <table>
        <thead><tr><th>Nome</th><th>Membri</th><th></th></tr></thead>
        <tbody>${otherList}</tbody>
      </table>
    </section>` : ""}`;
  }
  return alDetail;
}

/* ── F5: Chat ── */
function renderChat(ag, chat_delpy, chat_ugnet) {
  const delpyMsgs = (chat_delpy||[]).map(m =>
    `<div style="padding:4px 0;border-bottom:1px solid var(--border)">
      <small class="muted">${new Date(m.created_at).toLocaleTimeString()}</small>
      <span class="pill warn">Delpy</span>
      <span>${m.body}</span>
    </div>`).join("") || '<p class="muted">Nessun messaggio di sistema.</p>';

  const ugMsgs = (chat_ugnet||[]).map(m =>
    `<div style="padding:4px 0;border-bottom:1px solid var(--border)">
      <small class="muted">${new Date(m.created_at).toLocaleTimeString()}</small>
      <span class="pill">${m.author_agency_id ? "Agenzia #"+m.author_agency_id : "Sistema"}</span>
      <span>${m.body}</span>
    </div>`).join("") || '<p class="muted">Nessun messaggio.</p>';

  const alKey = ag.alliance_id ? String(ag.alliance_id) : null;

  return `
  <section class="card">
    <h2>Canale Delpy (sistema)</h2>
    <div style="max-height:200px;overflow-y:auto;padding:8px;background:var(--surface2);border-radius:6px">
      ${delpyMsgs}
    </div>
  </section>
  <section class="card">
    <h2>UG-Net (globale)</h2>
    <div style="max-height:200px;overflow-y:auto;padding:8px;background:var(--surface2);border-radius:6px;margin-bottom:10px">
      ${ugMsgs}
    </div>
    <div class="row">
      <input id="ugMsg" placeholder="Messaggio a UG-Net..." style="flex:3"/>
      <button onclick="doSendChat('ug_net','global')">Invia</button>
    </div>
    <div id="chat-err" class="err"></div>
  </section>
  ${ag.alliance_id ? `
  <section class="card">
    <h2>Canale Alleanza (privato)</h2>
    <div id="al-chat-feed" style="max-height:200px;overflow-y:auto;padding:8px;background:var(--surface2);border-radius:6px;margin-bottom:10px">
      <p class="muted">Caricamento...</p>
    </div>
    <div class="row">
      <input id="alMsg" placeholder="Messaggio alleanza..." style="flex:3"/>
      <button onclick="doSendChat('alleanza','${alKey}')">Invia</button>
    </div>
  </section>` : ""}`;
}

/* ── main dashboard builder ── */
function viewDashboard(ag, pilots, fighters, vehicles, missions) {
  const { classifica, alliance, chat_delpy, chat_ugnet } = S.data;
  const tabs = [
    { id: "overview", label: "Panoramica" },
    { id: "buildings", label: "Edifici" },
    { id: "pilots", label: `Piloti (${pilots.length})` },
    { id: "fighters", label: `Combattenti (${fighters.length})` },
    { id: "vehicles", label: `Vettori (${vehicles.length})` },
    { id: "missions", label: `Missioni (${missions.filter(m=>m.status==="assigned").length})` },
    { id: "classifica", label: "Classifica" },
    { id: "alleanze", label: ag.alliance_id ? "Alleanza ✦" : "Alleanze" },
    { id: "chat", label: "Chat" },
    { id: "shop", label: "Shop 🛡" },
  ];
  const tabBar = tabs.map(t =>
    `<button class="tab${S.tab===t.id?" active":""}" onclick="switchTab('${t.id}')">${t.label}</button>`
  ).join("");

  let content = "";
  if (S.tab === "overview") content = renderOverview(ag);
  else if (S.tab === "buildings") content = renderBuildings(ag);
  else if (S.tab === "pilots") content = renderPilots(pilots);
  else if (S.tab === "fighters") content = renderFighters(fighters);
  else if (S.tab === "vehicles") content = renderVehicles(vehicles, pilots);
  else if (S.tab === "missions") content = renderMissions(missions, vehicles, fighters);
  else if (S.tab === "classifica") content = renderClassifica(classifica, ag.id);
  else if (S.tab === "alleanze") content = renderAlleanze(ag, alliance, classifica);
  else if (S.tab === "chat") content = renderChat(ag, chat_delpy, chat_ugnet);
  else if (S.tab === "shop") content = renderShop(ag, S.data.shopCatalog || [], S.data.shopPool || {}, S.data.shopTx || []);

  app().innerHTML = `
  <div class="tabs">${tabBar}</div>
  ${content}
  <section class="card"><h2>Log · Delpy</h2><div id="log" class="log">${S.log.join("\n")}</div></section>`;

  // carica messaggi alleanza se nel tab chat
  if (S.tab === "chat" && ag.alliance_id) {
    req(`/api/chat/${S.serverId}/messages/alleanza/${ag.alliance_id}`)
      .then(msgs => {
        const el = document.getElementById("al-chat-feed");
        if (!el) return;
        el.innerHTML = msgs.length
          ? msgs.map(m => `<div style="padding:4px 0;border-bottom:1px solid var(--border)">
              <small class="muted">${new Date(m.created_at).toLocaleTimeString()}</small>
              <span class="pill">${m.author_agency_id ? "Agenzia #"+m.author_agency_id : "Sistema"}</span>
              <span>${m.body}</span></div>`).join("")
          : '<p class="muted">Nessun messaggio nell\'alleanza.</p>';
      }).catch(() => {});
  }
}

function switchTab(tab) {
  S.tab = tab;
  viewDashboard(S.data.ag, S.data.pilots, S.data.fighters, S.data.vehicles, S.data.missions);
}

/* ────────────────────────── Actions ────────────────────────── */

async function doRecruit() {
  $("dashErr").textContent = "";
  try {
    const d = await req(`/api/agency/${S.serverId}/recruit`, { method: "POST", body: { option: $("recruitOpt").value } });
    logLine(`reclutati ${d.pilots.length} piloti, ${d.fighters.length} combattenti (-${d.cost} R)`);
    await refreshData();
  } catch (e) { $("dashErr").textContent = e.message; }
}

async function doTick() {
  try {
    const d = await req(`/api/admin/server/${S.serverId}/tick`, { method: "POST" });
    let msg = `tick → giorno ${d.day} · missioni: ${d.missioni_assegnate}`;
    if (d.taglio) {
      msg += ` · TAGLIO ciclo ${d.taglio.cycle-1}: ${d.taglio.tagliati.length} eliminati`;
    }
    logLine(msg);
    await refreshData();
  } catch (e) { logLine("tick err: " + e.message); }
}

/* Buildings */
async function upgradeBuilding(type) {
  const errEl = $(`err-${type}`);
  if (errEl) errEl.textContent = "";
  try {
    const d = await req(`/api/agency/${S.serverId}/buildings/${type}/upgrade`, { method: "POST" });
    logLine(`upgrade ${type}: ${JSON.stringify(d)}`);
    await refreshData();
  } catch (e) {
    if (errEl) errEl.textContent = e.message;
    else logLine(`err upgrade ${type}: ${e.message}`);
  }
}

/* Pilots — license training dialog */
function trainLicenseDialog(pilotId) {
  const d = document.getElementById("pilot-dialog");
  document.getElementById("dialog-title").textContent = "Addestramento Licenza";
  document.getElementById("dialog-content").innerHTML = `
    <div class="row">
      <div style="flex:1"><label>Tipo</label><select id="licType"><option>A</option><option>B</option><option>C</option><option>D</option><option>E</option></select></div>
      <div style="flex:1"><label>Tier</label><select id="licTier"><option>bronze</option><option>silver</option><option>gold</option><option>platinum</option></select></div>
      <button onclick="doTrainLicense(${pilotId})">Avvia</button>
    </div>
    <div id="lic-err" class="err"></div>`;
  d.style.display = "block";
}

async function doTrainLicense(pilotId) {
  $("lic-err").textContent = "";
  try {
    const d = await req(`/api/agency/${S.serverId}/pilots/${pilotId}/train-license`, {
      method: "POST", body: { license_type: $("licType").value, tier: $("licTier").value }
    });
    logLine(`licenza ${d.license_type}-${d.tier}: avviato per ${d.giorni_addestramento}gg (-${d.cost}R)`);
    closeDialog();
    await refreshData();
  } catch (e) { $("lic-err").textContent = e.message; }
}

/* Pilots — stat training dialog */
function trainStatDialog(pilotId) {
  document.getElementById("pilot-dialog").style.display = "block";
  document.getElementById("dialog-title").textContent = "Addestramento Stat (+1% · 1000R)";
  document.getElementById("dialog-content").innerHTML = `
    <div class="row">
      <select id="pStat"><option value="espo">ESPO</option><option value="str">STR</option><option value="strs">STRS</option></select>
      <button onclick="doTrainPilotStat(${pilotId})">Allena</button>
    </div>
    <div id="pstat-err" class="err"></div>`;
}

async function doTrainPilotStat(pilotId) {
  $("pstat-err").textContent = "";
  try {
    const d = await req(`/api/agency/${S.serverId}/pilots/${pilotId}/train-stat`, {
      method: "POST", body: { stat: $("pStat").value }
    });
    logLine(`pilota stat ${d.stat}: ${d.current_pct}% → ${d.new_pct_at_completion}% al giorno ${d.completamento_giorno}`);
    closeDialog(); await refreshData();
  } catch (e) { $("pstat-err").textContent = e.message; }
}

function closeDialog() { document.getElementById("pilot-dialog").style.display = "none"; }

/* Fighters */
async function hospitalize(fighterId) {
  try {
    await req(`/api/agency/${S.serverId}/fighters/${fighterId}/hospitalize`, { method: "POST" });
    logLine("combattente ricoverato in ospedale");
    await refreshData();
  } catch (e) {
    const el = $("fighter-err");
    if (el) el.textContent = e.message;
  }
}

async function discharge(fighterId) {
  try {
    await req(`/api/agency/${S.serverId}/fighters/${fighterId}/discharge`, { method: "POST" });
    logLine("combattente dimesso dall'ospedale");
    await refreshData();
  } catch (e) {
    const el = $("fighter-err");
    if (el) el.textContent = e.message;
  }
}

function trainFighterDialog(fighterId) {
  document.getElementById("fighter-dialog").style.display = "block";
  document.getElementById("fdialog-title").textContent = "Allena Combattente (+1 punto · 250R)";
  document.getElementById("fdialog-content").innerHTML = `
    <div class="row">
      <select id="fStat"><option>STR</option><option>DIF</option><option>MOV</option><option>SPA</option></select>
      <button onclick="doTrainFighter(${fighterId})">Allena</button>
    </div>
    <div id="ftrain-err" class="err"></div>`;
}

async function doTrainFighter(fighterId) {
  $("ftrain-err").textContent = "";
  try {
    const d = await req(`/api/agency/${S.serverId}/fighters/${fighterId}/train`, {
      method: "POST", body: { stat: $("fStat").value }
    });
    logLine(`combattente allena ${d.stat}: ${d.current_val} → ${d.new_val_at_completion} al giorno ${d.completamento_giorno}`);
    closeFDialog(); await refreshData();
  } catch (e) { $("ftrain-err").textContent = e.message; }
}

function equipDialog(fighterId) {
  document.getElementById("fighter-dialog").style.display = "block";
  document.getElementById("fdialog-title").textContent = "Equipaggiamento (§6.1)";
  const levels = ["bronze1","bronze2","bronze3","silver1","silver2","silver3","gold1","gold2","gold3"];
  const lOpts = levels.map(l => `<option>${l}</option>`).join("");
  document.getElementById("fdialog-content").innerHTML = `
    <div class="row">
      <select id="eSlot"><option value="weapon">Arma</option><option value="armor_terra">Armatura Terra</option><option value="armor_spazio">Armatura Spazio</option></select>
      <select id="eLvl" style="flex:2">${lOpts}</select>
      <button onclick="doEquip(${fighterId})">Equip</button>
      <button class="ghost sm" onclick="doEquipRemove(${fighterId})">Rimuovi</button>
    </div>
    <div id="equip-err" class="err"></div>`;
}

async function doEquip(fighterId) {
  $("equip-err").textContent = "";
  try {
    const d = await req(`/api/agency/${S.serverId}/fighters/${fighterId}/equip`, {
      method: "POST", body: { slot: $("eSlot").value, level_key: $("eLvl").value }
    });
    logLine(`equipaggiamento ${d.slot}=${d.level_key} (-${d.cost}R)`);
    closeFDialog(); await refreshData();
  } catch (e) { $("equip-err").textContent = e.message; }
}

async function doEquipRemove(fighterId) {
  $("equip-err").textContent = "";
  try {
    await req(`/api/agency/${S.serverId}/fighters/${fighterId}/equip`, {
      method: "POST", body: { slot: $("eSlot").value, level_key: "" }
    });
    logLine("equipaggiamento rimosso");
    closeFDialog(); await refreshData();
  } catch (e) { $("equip-err").textContent = e.message; }
}

function closeFDialog() { document.getElementById("fighter-dialog").style.display = "none"; }

/* Vehicles */
async function buyVehicle() {
  $("vehicle-err").textContent = "";
  try {
    const d = await req(`/api/agency/${S.serverId}/vehicles/buy`, {
      method: "POST", body: { project: $("buyProject").value }
    });
    logLine(`acquistato ${d.project} (${d.vclass}) -${d.cost}R`);
    await refreshData();
  } catch (e) { $("vehicle-err").textContent = e.message; }
}

function assignPilotDialog(vehicleId) {
  document.getElementById("vehicle-dialog").style.display = "block";
  document.getElementById("vdialog-title").textContent = "Assegna Pilota";
  const opts = S.data.pilots
    .filter(p => p.status !== "eliminated" && p.status !== "in_flight")
    .map(p => `<option value="${p.id}">${p.name} [${Object.entries(p.licenses).filter(([k])=>!k.startsWith("__")).map(([k,v])=>`${k.toUpperCase()}-${v}`).join(",")||"nessuna"}]</option>`)
    .join("");
  document.getElementById("vdialog-content").innerHTML = `
    <div class="row">
      <select id="apPilot" style="flex:2">${opts || '<option disabled>Nessun pilota disponibile</option>'}</select>
      <button onclick="doAssignPilot(${vehicleId})">Assegna</button>
      <button class="ghost sm" onclick="doUnassignPilot(${vehicleId})">Rimuovi pilota</button>
    </div>
    <div id="ap-err" class="err"></div>`;
}

async function doAssignPilot(vehicleId) {
  $("ap-err").textContent = "";
  try {
    await req(`/api/agency/${S.serverId}/vehicles/${vehicleId}/assign-pilot`, {
      method: "POST", body: { pilot_id: Number($("apPilot").value) }
    });
    logLine("pilota assegnato al vettore");
    closeVDialog(); await refreshData();
  } catch (e) { $("ap-err").textContent = e.message; }
}

async function doUnassignPilot(vehicleId) {
  try {
    await req(`/api/agency/${S.serverId}/vehicles/${vehicleId}/unassign-pilot`, { method: "POST" });
    logLine("pilota rimosso dal vettore");
    closeVDialog(); await refreshData();
  } catch (e) {
    const el = $("ap-err");
    if (el) el.textContent = e.message;
  }
}

function missilesDialog(vehicleId) {
  document.getElementById("vehicle-dialog").style.display = "block";
  document.getElementById("vdialog-title").textContent = "Carica Missili (§6.2 · max 4 totali)";
  document.getElementById("vdialog-content").innerHTML = `
    <div class="row">
      <select id="misKey"><option>bronze</option><option>silver</option><option>gold</option><option>platinum</option></select>
      <input id="misCount" type="number" min="0" max="4" value="2" style="width:70px"/>
      <select id="misType"><option value="terra">Terra</option><option value="spazio">Spazio</option></select>
      <button onclick="doLoadMissiles(${vehicleId})">Carica</button>
    </div>
    <div id="mis-err" class="err"></div>`;
}

async function doLoadMissiles(vehicleId) {
  $("mis-err").textContent = "";
  try {
    const d = await req(`/api/agency/${S.serverId}/vehicles/${vehicleId}/missiles`, {
      method: "POST", body: {
        missile_key: $("misKey").value,
        count: Number($("misCount").value),
        missile_type: $("misType").value,
      }
    });
    logLine(`missili caricati: terra ${d.missiles.terra.count}× ${d.missiles.terra.key||"—"}, spazio ${d.missiles.spazio.count}× ${d.missiles.spazio.key||"—"} (-${d.cost}R)`);
    closeVDialog(); await refreshData();
  } catch (e) { $("mis-err").textContent = e.message; }
}

function closeVDialog() { document.getElementById("vehicle-dialog").style.display = "none"; }

/* Missions — launch dialog */
function launchDialog(missionId, mtype) {
  S._launchMid = missionId;
  S._launchIsIntercept = mtype.startsWith("intercept");
  S._launchIsEvac = mtype === "evacuazione";
  const classMap = {
    terrestre: "mission", lunare: "space_mission",
    intercept_terra: "fighter", intercept_luna: "space_fighter",
    evacuazione: "civilian",
  };
  const needed = classMap[mtype];
  const vs = S.data.vehicles.filter(v => v.status === "barracks" && (!needed || v.vclass === needed));
  const vOpts = vs.map(v => `<option value="${v.id}">${v.project} (${v.vclass})</option>`).join("");
  const avail = S.data.fighters.filter(f => f.status === "barracks");
  const fGrid = avail.map(f => `
    <label style="display:inline-flex;gap:6px;align-items:center;padding:4px 8px;border:1px solid var(--border);border-radius:4px;cursor:pointer">
      <input type="checkbox" class="f-sel" value="${f.id}" />
      ${f.name} (TABI ${f.tabi})
    </label>`).join(" ");

  // chain: missioni assegnate compatibili con lo stesso tipo vettore
  const chainable = S.data.missions.filter(m =>
    m.status === "assigned" && m.id !== missionId &&
    (classMap[m.mission_type] === needed || !needed)
  );
  const chainOpts = chainable.map(m =>
    `<option value="${m.id}">[${m.alarm.toUpperCase()}] ${_mtypeLabel(m.mission_type)} (Pn ${m.pn}, gg${m.deadline_day})</option>`
  ).join("");

  $("launch-content").innerHTML = `
    <div class="row" style="margin-bottom:10px">
      <div style="flex:2"><label>Vettore</label>
        <select id="lVehicle" style="width:100%" onchange="doSimulate(${missionId})">${vOpts || '<option disabled>Nessun vettore adatto disponibile</option>'}</select>
      </div>
      <button class="sm ghost" style="align-self:flex-end" onclick="doSimulate(${missionId})">Simula</button>
    </div>
    ${!S._launchIsIntercept && !S._launchIsEvac ? `
    <div style="margin-bottom:10px">
      <label>Combattenti:</label>
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px">${fGrid || '<span class="muted">Nessun combattente disponibile</span>'}</div>
    </div>` : ""}
    ${!S._launchIsEvac && chainable.length ? `
    <div style="margin-bottom:10px;padding:8px;border:1px solid var(--border);border-radius:6px">
      <label>Catena sortie §9.11 (opzionale — aggiungi tappe):</label>
      <select id="lChain" multiple style="width:100%;height:80px;margin-top:4px">${chainOpts}</select>
      <small class="muted">Ctrl+click per selezionare più tappe (max ${3})</small>
    </div>` : ""}`;
  $("sim-result").innerHTML = "";
  $("launch-err").textContent = "";
  $("launch-dialog").style.display = "block";
}

async function doSimulate(missionId) {
  const vidEl = $("lVehicle");
  if (!vidEl || !vidEl.value) return;
  const fids = Array.from(document.querySelectorAll(".f-sel:checked")).map(e => e.value).join(",");
  try {
    const d = await req(`/api/agency/${S.serverId}/missions/${missionId}/simulate?vehicle_id=${vidEl.value}&fighter_ids=${fids}`);
    const pct = Math.round(d.prob_successo * 100);
    const cls = pct >= 70 ? "ok" : pct >= 40 ? "warn" : "bad";
    $("sim-result").innerHTML = `
      <div style="background:var(--surface2);border-radius:6px;padding:10px">
        <div class="grid">
          <div class="stat"><div class="k">Pg (tuo)</div><div class="v ok">${d.pg} <small class="muted">[${d.pg_min}–${d.pg_max}]</small></div></div>
          <div class="stat"><div class="k">Pn (nemico)</div><div class="v bad">${d.pn} <small class="muted">[${d.pn_min}–${d.pn_max}]</small></div></div>
          <div class="stat"><div class="k">Prob. Successo</div><div class="v ${cls}">${pct}%</div></div>
        </div>
      </div>`;
  } catch (e) { $("sim-result").innerHTML = `<small class="bad">${e.message}</small>`; }
}

async function doLaunchMission() {
  $("launch-err").textContent = "";
  const vid = Number($("lVehicle")?.value || 0);
  if (!vid) { $("launch-err").textContent = "Seleziona un vettore"; return; }
  const fids = Array.from(document.querySelectorAll(".f-sel:checked")).map(e => Number(e.value));
  // chain legs: each selected chain mission gets the same fighter selection
  const chainEl = $("lChain");
  const chainLegs = chainEl
    ? Array.from(chainEl.selectedOptions).map(opt => ({ mission_id: Number(opt.value), fighter_ids: fids }))
    : [];
  try {
    const d = await req(`/api/agency/${S.serverId}/missions/${S._launchMid}/launch`, {
      method: "POST", body: { vehicle_id: vid, fighter_ids: fids, chain_legs: chainLegs }
    });
    const chain = d.chain_legs ? ` (catena ${d.chain_legs + 1} tappe)` : "";
    logLine(`missione #${d.mission_id} lanciata${chain} · ETA ${d.eta_days.toFixed(1)} gg · rientro gg ${d.return_day.toFixed(1)}`);
    closeLDialog(); await refreshData();
  } catch (e) { $("launch-err").textContent = e.message; }
}

function closeLDialog() { $("launch-dialog").style.display = "none"; }

/* ────────────────────────── Data refresh ────────────────────────── */
async function refreshData() {
  const sid = S.serverId;
  const [ag, pilots, fighters, vehicles, missions, classifica, chat_delpy, chat_ugnet] = await Promise.all([
    req(`/api/agency/${sid}`),
    req(`/api/agency/${sid}/pilots`).catch(() => []),
    req(`/api/agency/${sid}/fighters`).catch(() => []),
    req(`/api/agency/${sid}/vehicles`).catch(() => []),
    req(`/api/agency/${sid}/missions`).catch(() => []),
    req(`/api/classifica/${sid}`).catch(() => []),
    req(`/api/chat/${sid}/messages/delpy/sistema`).catch(() => []),
    req(`/api/chat/${sid}/messages/ug_net/global`).catch(() => []),
  ]);
  let alliance = null;
  if (ag.alliance_id) {
    alliance = await req(`/api/alliances/${ag.alliance_id}/detail?server_id=${sid}`).catch(() => null);
    if (!alliance) {
      // fallback: recupera dalla lista
      const list = await req(`/api/alliances/${sid}`).catch(() => []);
      alliance = list.find(a => a.id === ag.alliance_id) || null;
    }
  }
  // carica dati shop solo se necessario
  let shopCatalog = S.data.shopCatalog || [];
  let shopPool = S.data.shopPool || {};
  let shopTx = S.data.shopTx || [];
  if (S.tab === "shop" || !shopCatalog.length) {
    [shopCatalog, shopPool, shopTx] = await Promise.all([
      req("/api/catalog/shop").catch(() => []),
      req(`/api/shop/${sid}/pool`).catch(() => ({})),
      req(`/api/shop/${sid}/transactions`).catch(() => []),
    ]);
  }

  S.data = { ag, pilots, fighters, vehicles, missions, classifica, alliance,
             chat_delpy, chat_ugnet, shopCatalog, shopPool, shopTx };
  viewDashboard(ag, pilots, fighters, vehicles, missions);
}

/* ────────────────────────── F6: Shop actions ────────────────────────── */
async function doBuyPackage(packageKey) {
  const errEl = $("shop-err");
  if (errEl) errEl.textContent = "";
  try {
    const d = await req("/api/shop/purchase", {
      method: "POST", body: { server_id: Number(S.serverId), package_key: packageKey }
    });
    logLine(`acquistato "${packageKey}" (${d.price_eur}€ · Agenda 2030: ${d.agenda_2030_eur}€) · pool: ${d.pool_size} unità`);
    // forza reload shop data
    S.data.shopCatalog = [];
    await refreshData();
  } catch (e) {
    const el = $("shop-err");
    if (el) el.textContent = e.message;
    else logLine("shop err: " + e.message);
  }
}

async function doRedeem(unitType) {
  const errEl = $("shop-pool-err");
  if (errEl) errEl.textContent = "";
  try {
    const d = await req(`/api/shop/${S.serverId}/redeem`, {
      method: "POST", body: { unit_type: unitType }
    });
    const label = unitType === "vehicle"
      ? `vettore ${d.project}`
      : `${unitType} "${d.name}"`;
    logLine(`riscattato ${label} dal pool · rimaste ${d.pool_remaining} unità`);
    S.data.shopCatalog = [];
    await refreshData();
  } catch (e) {
    const el = $("shop-pool-err");
    if (el) el.textContent = e.message;
    else logLine("redeem err: " + e.message);
  }
}

/* ────────────────────────── F5: Alliance actions ────────────────────────── */
async function doCreateAlliance() {
  const errEl = $("al-err");
  if (errEl) errEl.textContent = "";
  try {
    const name = $("alName")?.value?.trim();
    if (!name) throw new Error("inserisci un nome");
    const d = await req("/api/alliances", { method: "POST", body: { server_id: Number(S.serverId), name } });
    logLine(`alleanza "${d.name}" creata (id #${d.id})`);
    await refreshData();
  } catch (e) {
    const el = $("al-err");
    if (el) el.textContent = e.message;
    else logLine("err alleanza: " + e.message);
  }
}

async function doJoinAlliance(allianceId) {
  try {
    const d = await req(`/api/alliances/${allianceId}/join?server_id=${S.serverId}`, { method: "POST" });
    logLine(`entrato nell'alleanza "${d.name}"`);
    await refreshData();
  } catch (e) { logLine("err join alleanza: " + e.message); }
}

async function doLeaveAlliance() {
  if (!confirm("Sei sicuro di voler lasciare l'alleanza?")) return;
  try {
    const alId = S.data.ag.alliance_id;
    await req(`/api/alliances/${alId}/leave?server_id=${S.serverId}`, { method: "DELETE" });
    logLine("hai lasciato l'alleanza");
    await refreshData();
  } catch (e) { logLine("err leave alleanza: " + e.message); }
}

async function doAllianceDeposit() {
  const errEl = $("al-err");
  if (errEl) errEl.textContent = "";
  try {
    const amount = Number($("alDepositAmt")?.value || 0);
    const alId = S.data.ag.alliance_id;
    const d = await req(`/api/alliances/${alId}/treasury/deposit?server_id=${S.serverId}`, {
      method: "POST", body: { amount }
    });
    logLine(`depositati ${amount} R in tesoreria · tesoreria: ${d.treasury} R`);
    await refreshData();
  } catch (e) {
    const el = $("al-err");
    if (el) el.textContent = e.message;
  }
}

async function doAllianceWithdraw() {
  const errEl = $("al-err");
  if (errEl) errEl.textContent = "";
  try {
    const amount = Number($("alDepositAmt")?.value || 0);
    const alId = S.data.ag.alliance_id;
    const d = await req(`/api/alliances/${alId}/treasury/withdraw?server_id=${S.serverId}`, {
      method: "POST", body: { amount }
    });
    logLine(`prelevati ${amount} R dalla tesoreria · tesoreria: ${d.treasury} R`);
    await refreshData();
  } catch (e) {
    const el = $("al-err");
    if (el) el.textContent = e.message;
  }
}

async function doTransferMission(missionId) {
  try {
    const alId = S.data.ag.alliance_id;
    if (!alId) throw new Error("non sei in un'alleanza");
    await req(`/api/alliances/${alId}/transfer-mission?server_id=${S.serverId}`, {
      method: "POST", body: { mission_id: missionId }
    });
    logLine(`missione #${missionId} trasferita al pool alleanza`);
    await refreshData();
  } catch (e) { logLine("err trasferimento: " + e.message); }
}

/* ────────────────────────── F5: Chat actions ────────────────────────── */
async function doSendChat(channelType, channelKey) {
  const errEl = $("chat-err");
  if (errEl) errEl.textContent = "";
  const inputId = channelType === "ug_net" ? "ugMsg" : "alMsg";
  const body = $(inputId)?.value?.trim();
  if (!body) return;
  try {
    await req(`/api/chat/${S.serverId}/messages`, {
      method: "POST", body: { channel_type: channelType, channel_key: channelKey, body }
    });
    $(inputId).value = "";
    logLine(`messaggio inviato su ${channelType}`);
    await refreshData();
  } catch (e) {
    const el = $("chat-err");
    if (el) el.textContent = e.message;
  }
}

/* ────────────────────────── Boot ────────────────────────── */
async function boot() {
  $("who").textContent = S.token ? "● autenticato" : "";
  if (!S.token) return viewAuth();
  try { S.cultures = await req("/api/catalog/cultures"); } catch (e) { return viewAuth(); }
  try { S.recruit_opts = await req("/api/catalog/recruit-options"); } catch (e) {}
  try { S.vehicles_catalog = await req("/api/catalog/vehicles"); } catch (e) {}
  if (!S.serverId) return viewSetup();
  try {
    await refreshData();
  } catch (e) {
    viewSetup();
  }
}

window.addEventListener("DOMContentLoaded", () => {
  const saved = localStorage.getItem("sx_api");
  if (saved) $("apiBase").value = saved;
  $("apiBase").addEventListener("change", () => localStorage.setItem("sx_api", $("apiBase").value));
  boot();
});
