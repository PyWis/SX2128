/* SX2128 — Console Agenzia (SPA vanilla)
   Slice F0+F1: registrazione/login, server, agenzia, reclutamento, tick.
   Comunica con il backend FastAPI (vedi backend/). */

const S = {
  token: localStorage.getItem("sx_token") || null,
  serverId: localStorage.getItem("sx_server") || null,
  cultures: [],
  log: [],
};

const api = () => document.getElementById("apiBase").value.replace(/\/$/, "");
const $ = (id) => document.getElementById(id);
const app = () => document.getElementById("app");

function logLine(msg) {
  S.log.unshift(`[${new Date().toLocaleTimeString()}] ${msg}`);
  S.log = S.log.slice(0, 60);
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
  } else if (body) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(api() + path, { method, headers, body: payload });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ? JSON.stringify(data.detail) : res.status);
  return data;
}

/* ---------- Viste ---------- */
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

function viewSetup() {
  const opts = S.cultures.map(c => `<option value="${c.id}">${c.emoji} ${c.nome} — ${c.base_r_giorno} R/g · +${c.fedelta_pct_giorno}%/g</option>`).join("");
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
  <section class="card"><h2>Log di sistema · Delpy</h2><div id="log" class="log"></div></section>`;
  logLine("seleziona/crea un server e fonda l'agenzia");
}

async function createServer() {
  try {
    const d = await req("/api/admin/server", { method: "POST", body: { name: $("srvName").value, server_type: $("srvType").value } });
    S.serverId = d.id; localStorage.setItem("sx_server", d.id);
    logLine(`server #${d.id} "${d.name}" creato (giorno ${d.day})`);
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

function stat(k, v, cls = "") { return `<div class="stat"><div class="k">${k}</div><div class="v ${cls}">${v}</div></div>`; }

function viewDashboard(ag) {
  const recruitOpts = Object.entries(S.recruit || {}).map(([k, v]) =>
    `<option value="${k}">${k.replaceAll("_", " ")} — ${v.cost} R</option>`).join("");
  app().innerHTML = `
  <section class="card">
    <h2>${ag.name} <span class="pill">${ag.culture}</span> ${ag.in_default ? '<span class="pill bad">DEFAULT</span>' : ''}</h2>
    <div class="grid">
      ${stat("Saldo (R)", Math.round(ag.balance), ag.balance < 0 ? "bad" : "ok")}
      ${stat("Fedeltà (gg)", ag.loyalty_days)}
      ${stat("ESPO oggi", Math.round(ag.espo_today))}
      ${stat("ESPO totale", Math.round(ag.espo_total))}
      ${stat("Missioni", ag.missions_completed)}
      ${stat("Caserma", ag.barracks_capacity)}
      ${stat("Ospedale", ag.hospital_capacity)}
      ${stat("Hangar", ag.hangar_slots)}
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
  </section>
  <section class="card"><h2>Log di sistema · Delpy</h2><div id="log" class="log"></div></section>`;
  $("log").textContent = S.log.join("\n");
}

async function doRecruit() {
  $("dashErr").textContent = "";
  try {
    const d = await req(`/api/agency/${S.serverId}/recruit`, { method: "POST", body: { option: $("recruitOpt").value } });
    logLine(`reclutati ${d.pilots.length} piloti, ${d.fighters.length} combattenti (-${d.cost} R)`);
    await boot();
  } catch (e) { $("dashErr").textContent = e.message; }
}
async function doTick() {
  try {
    const d = await req(`/api/admin/server/${S.serverId}/tick`, { method: "POST" });
    logLine(`tick → giorno ${d.day} · missioni assegnate: ${d.missioni_assegnate}`);
    await boot();
  } catch (e) { logLine("tick err: " + e.message); }
}

/* ---------- Boot / routing ---------- */
async function boot() {
  $("who").textContent = S.token ? "● autenticato" : "";
  if (!S.token) return viewAuth();
  try { S.cultures = await req("/api/catalog/cultures"); } catch (e) { return viewAuth(); }
  try { S.recruit = await req("/api/catalog/recruit-options"); } catch (e) {}
  if (!S.serverId) return viewSetup();
  try {
    const ag = await req(`/api/agency/${S.serverId}`);
    viewDashboard(ag);
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
