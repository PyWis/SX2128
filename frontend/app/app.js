/* SX2128 — Console Agenzia (SPA vanilla)
   F2: Personale, Edifici, Vettori, Equipaggiamento */

const S = {
  token: localStorage.getItem("sx_token") || null,
  serverId: localStorage.getItem("sx_server") || null,
  cultures: [],
  vehicles_catalog: [],
  recruit_opts: {},
  log: [],
  tab: "overview",
  data: { ag: null, pilots: [], fighters: [], vehicles: [] },
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

/* ── main dashboard builder ── */
function viewDashboard(ag, pilots, fighters, vehicles) {
  const tabs = [
    { id: "overview", label: "Panoramica" },
    { id: "buildings", label: "Edifici" },
    { id: "pilots", label: `Piloti (${pilots.length})` },
    { id: "fighters", label: `Combattenti (${fighters.length})` },
    { id: "vehicles", label: `Vettori (${vehicles.length})` },
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

  app().innerHTML = `
  <div class="tabs">${tabBar}</div>
  ${content}
  <section class="card"><h2>Log · Delpy</h2><div id="log" class="log">${S.log.join("\n")}</div></section>`;
}

function switchTab(tab) {
  S.tab = tab;
  viewDashboard(S.data.ag, S.data.pilots, S.data.fighters, S.data.vehicles);
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
    logLine(`tick → giorno ${d.day} · missioni assegnate: ${d.missioni_assegnate}`);
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

/* ────────────────────────── Data refresh ────────────────────────── */
async function refreshData() {
  const sid = S.serverId;
  const [ag, pilots, fighters, vehicles] = await Promise.all([
    req(`/api/agency/${sid}`),
    req(`/api/agency/${sid}/pilots`).catch(() => []),
    req(`/api/agency/${sid}/fighters`).catch(() => []),
    req(`/api/agency/${sid}/vehicles`).catch(() => []),
  ]);
  S.data = { ag, pilots, fighters, vehicles };
  viewDashboard(ag, pilots, fighters, vehicles);
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
