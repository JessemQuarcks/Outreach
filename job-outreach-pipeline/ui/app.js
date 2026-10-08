"use strict";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

async function api(path, opts) {
  const res = await fetch(path, opts);
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    const msg = (data && data.error) || `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return data;
}
const postJSON = (path, body) =>
  api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });

function toast(msg, isErr) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.toggle("err", !!isErr);
  t.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add("hidden"), 3200);
}

/* ---------- Navigation ---------- */
function showView(name) {
  $$(".view").forEach(v => v.classList.toggle("active", v.id === `view-${name}`));
  $$(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.view === name));
  const loaders = {
    dashboard: loadDashboard, queue: loadQueue, followups: loadFollowups,
    letters: loadLetters, logs: loadLogs, settings: loadSettings,
  };
  if (loaders[name]) loaders[name]();
}
$("#nav").addEventListener("click", e => {
  const btn = e.target.closest(".nav-item");
  if (btn) showView(btn.dataset.view);
});
document.addEventListener("click", e => {
  const g = e.target.closest("[data-goto]");
  if (g) showView(g.dataset.goto);
});

/* ---------- Theme ---------- */
(function initTheme() {
  const saved = localStorage.getItem("theme");
  if (saved) document.documentElement.setAttribute("data-theme", saved);
})();
$("#theme-toggle").addEventListener("click", () => {
  const cur = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", cur);
  localStorage.setItem("theme", cur);
});

/* ---------- Dashboard ---------- */
const STAT_META = [
  { key: "total", label: "Total companies", accent: "#77216F", from: "total" },
  { key: "Pending", label: "Pending", accent: "#8a8f9c" },
  { key: "Approved", label: "Approved", accent: "#1a9e5f", sub: "ready to send" },
  { key: "Sent", label: "Sent", accent: "#77216F" },
  { key: "Followup-Sent", label: "Followed up", accent: "#E95420" },
  { key: "Failed", label: "Failed", accent: "#d9402b" },
  { key: "Skipped", label: "Skipped", accent: "#8a8f9c" },
];

async function loadDashboard() {
  let s;
  try { s = await api("/api/status"); }
  catch (e) { toast(e.message, true); return; }

  const grid = $("#stat-grid");
  grid.innerHTML = STAT_META.map(m => {
    const val = m.from === "total" ? s.total : (s.stats[m.key] || 0);
    let sub = m.sub || "";
    if (m.key === "Pending" && s.no_email) sub = `${s.no_email} without an email`;
    return `<div class="stat" style="--accent:${m.accent}">
      <div class="num">${val}</div>
      <div class="label">${m.label}</div>
      ${sub ? `<div class="sub">${sub}</div>` : ""}
    </div>`;
  }).join("");

  // Setup checklist
  const creds = s.credentials || {};
  const items = [
    ["EXA_API_KEY", "Exa search key", creds.EXA_API_KEY],
    ["APIFY_API_TOKEN", "Apify scraper token", creds.APIFY_API_TOKEN],
    ["SENDER_EMAIL", "Sender email", creds.SENDER_EMAIL],
    ["GMAIL_APP_PASSWORD", "Gmail app password", creds.GMAIL_APP_PASSWORD],
    ["CV", `CV file (${s.cv_path || "not set"})`, s.cv_exists],
  ];
  $("#checklist").innerHTML = items.map(([k, label, ok]) =>
    `<li><span class="check-ic ${ok ? "yes" : "no"}">${ok ? "✓" : "–"}</span>
      <span>${label}</span></li>`).join("");

  const missing = items.filter(i => !i[2]).length;
  const banner = $("#setup-banner");
  if (missing > 0) {
    banner.className = "banner warn";
    banner.innerHTML = `<b>${missing} setup item${missing > 1 ? "s" : ""} still needed.</b>
      Add your API keys, email credentials and CV on the <b>Settings</b> page before running the pipeline.`;
    banner.classList.remove("hidden");
  } else {
    banner.classList.add("hidden");
  }
}

/* ---------- Queue ---------- */
let QUEUE_CACHE = [];
async function loadQueue() {
  let data;
  try { data = await api("/api/queue"); }
  catch (e) { toast(e.message, true); return; }
  QUEUE_CACHE = data.rows;
  renderQueue();
  updateSendNote();
}

function renderQueue() {
  const filter = ($("#queue-filter").value || "").toLowerCase();
  const body = $("#queue-body");
  const statuses = ["Pending", "Approved", "Sent", "Failed", "Skipped", "Followup-Sent"];
  const rows = QUEUE_CACHE.filter(r =>
    !filter || [r.company_name, r.email, r.status, r.website].some(v => (v || "").toLowerCase().includes(filter)));

  $("#queue-empty").classList.toggle("hidden", QUEUE_CACHE.length !== 0);
  body.innerHTML = rows.map(r => {
    const opts = statuses.map(s => `<option value="${s}" ${s === r.status ? "selected" : ""}>${s}</option>`).join("");
    return `<tr data-i="${r._i}">
      <td><input class="cell-input" data-f="company_name" value="${esc(r.company_name)}"></td>
      <td><input class="cell-input" data-f="website" value="${esc(r.website)}"></td>
      <td><input class="cell-input" data-f="email" value="${esc(r.email)}" placeholder="—"></td>
      <td><input class="cell-input" data-f="company_type" value="${esc(r.company_type)}" style="min-width:110px"></td>
      <td><input class="cell-input" data-f="recipient_name" value="${esc(r.recipient_name)}"></td>
      <td><select class="status-select" data-status="${esc(r.status)}">${opts}</select></td>
      <td class="muted small">${esc(r.date_added)}</td>
      <td class="muted small">${esc((r.date_sent || "").split("|")[0])}</td>
      <td><button class="row-del" title="Delete">✕</button></td>
    </tr>`;
  }).join("");
}

function esc(s) { return String(s == null ? "" : s).replace(/"/g, "&quot;").replace(/</g, "&lt;"); }

$("#queue-filter").addEventListener("input", renderQueue);

$("#queue-body").addEventListener("change", async e => {
  const tr = e.target.closest("tr");
  if (!tr) return;
  const i = parseInt(tr.dataset.i, 10);
  if (e.target.matches(".cell-input")) {
    const payload = { _i: i, [e.target.dataset.f]: e.target.value };
    try { await postJSON("/api/queue/update", payload); toast("Saved"); }
    catch (err) { toast(err.message, true); }
  } else if (e.target.matches(".status-select")) {
    e.target.dataset.status = e.target.value;
    try {
      await postJSON("/api/queue/update", { _i: i, status: e.target.value });
      const row = QUEUE_CACHE.find(r => r._i === i); if (row) row.status = e.target.value;
      updateSendNote(); toast("Status updated");
    } catch (err) { toast(err.message, true); }
  }
});

$("#queue-body").addEventListener("click", async e => {
  if (!e.target.matches(".row-del")) return;
  const tr = e.target.closest("tr");
  const i = parseInt(tr.dataset.i, 10);
  const row = QUEUE_CACHE.find(r => r._i === i);
  confirmAction("Delete company?", `Remove “${row ? row.company_name : "this company"}” from the queue? This can't be undone.`, async () => {
    try { await postJSON("/api/queue/delete", { _i: i }); await loadQueue(); toast("Deleted"); }
    catch (err) { toast(err.message, true); }
  });
});

$("#approve-scraped").addEventListener("click", () => {
  confirmAction("Approve all with an email?",
    "Every Pending company that has an email address will be marked Approved and become eligible to send. Continue?",
    async () => {
      try {
        const r = await postJSON("/api/queue/bulk", { to_status: "Approved", from_status: "Pending", require_email: true });
        await loadQueue(); toast(`${r.changed} companies approved`);
      } catch (err) { toast(err.message, true); }
    }, "Approve");
});

/* Add company modal */
$("#add-company-btn").addEventListener("click", () => openModal("add-modal"));
$("#add-save").addEventListener("click", async () => {
  const name = $("#add-name").value.trim();
  $("#add-err").textContent = "";
  if (!name) { $("#add-err").textContent = "Company name is required."; return; }
  try {
    await postJSON("/api/queue/add", {
      company_name: name,
      website: $("#add-website").value,
      email: $("#add-email").value,
      recipient_name: $("#add-recipient").value,
      company_type: $("#add-type").value,
      company_address: $("#add-address").value,
    });
    closeModals();
    ["add-name", "add-website", "add-email", "add-recipient", "add-address"].forEach(id => $("#" + id).value = "");
    await loadQueue(); toast("Company added");
  } catch (err) { $("#add-err").textContent = err.message; }
});

function updateSendNote() {
  const approved = QUEUE_CACHE.filter(r => r.status === "Approved" && r.email).length;
  const note = $("#send-ready-note");
  if (!note) return;
  note.textContent = approved
    ? `${approved} compan${approved === 1 ? "y is" : "ies are"} approved and ready to send (max 15 per run).`
    : "No companies are approved yet. Approve targets on the Queue page first.";
}

/* ---------- Follow-ups ---------- */
async function loadFollowups() {
  let data;
  try { data = await api("/api/followups/preview"); }
  catch (e) { toast(e.message, true); $("#followup-empty").classList.remove("hidden"); return; }
  const list = data.candidates || [];
  $("#followup-count").textContent = list.length;
  $("#followup-empty").classList.toggle("hidden", list.length !== 0);
  $("#followup-body").innerHTML = list.map(c =>
    `<tr><td>${esc(c.company_name)}</td><td>${esc(c.email)}</td><td class="muted">${esc(c.date_sent)}</td></tr>`).join("");
}
$("#followup-refresh").addEventListener("click", loadFollowups);
$("#followup-send").addEventListener("click", () => {
  confirmAction("Send follow-up emails?",
    "This will send live in-thread follow-up emails to up to 10 eligible companies, with a 30–60s delay between each. Continue?",
    async () => {
      showView("actions");
      try { await postJSON("/api/action/followup", { dry_run: false }); startPolling(); }
      catch (err) { toast(err.message, true); }
    }, "Send follow-ups");
});

/* ---------- Letters ---------- */
async function loadLetters() {
  let data;
  try { data = await api("/api/letters"); }
  catch (e) { toast(e.message, true); return; }
  const items = data.letters || [];
  $("#letters-empty").classList.toggle("hidden", items.length !== 0);
  $("#letters-grid").innerHTML = items.map(l =>
    `<a class="letter-card" href="/api/letters/${encodeURIComponent(l.name)}" target="_blank" rel="noopener">
      <div class="letter-ic">📄</div>
      <div class="letter-name">${esc(l.name)}</div>
      <div class="letter-meta">${l.size_kb} KB · ${esc(l.modified)}</div>
    </a>`).join("");
}
$("#letters-refresh").addEventListener("click", loadLetters);

/* ---------- Logs ---------- */
async function loadLogs() {
  let data;
  try { data = await api("/api/logs"); }
  catch (e) { toast(e.message, true); return; }
  const rows = data.rows || [];
  $("#logs-empty").classList.toggle("hidden", rows.length !== 0);
  $("#logs-body").innerHTML = rows.map(r => {
    const st = (r.status || "").toUpperCase();
    const color = st === "SUCCESS" ? "var(--ok)" : "var(--danger)";
    return `<tr>
      <td class="muted small">${esc(r.date)}</td>
      <td>${esc(r.company_name)}</td>
      <td>${esc(r.email)}</td>
      <td style="color:${color};font-weight:600">${esc(r.status)}</td>
      <td class="muted small">${esc(r.cover_letter)}</td>
    </tr>`;
  }).join("");
}
$("#logs-refresh").addEventListener("click", loadLogs);

/* ---------- Settings ---------- */
async function loadSettings() {
  let data;
  try { data = await api("/api/config"); }
  catch (e) { toast(e.message, true); return; }
  const cfg = data.config || {};
  const form = $("#settings-form");
  Object.entries(cfg).forEach(([k, v]) => {
    const input = form.elements[k];
    if (!input) return;
    if (v.secret) {
      input.value = "";
      input.placeholder = v.set ? "•••••••• (saved — leave blank to keep)" : input.placeholder;
    } else {
      input.value = v.value || "";
    }
  });
  $$(".set-tag[data-tag]").forEach(tag => {
    const k = tag.dataset.tag;
    const set = cfg[k] && cfg[k].set;
    tag.textContent = set ? "set" : "not set";
    tag.className = "set-tag " + (set ? "yes" : "no");
  });
  const cvTag = $("#cv-status");
  cvTag.textContent = data.cv_exists ? "file found" : "file missing";
  cvTag.className = "set-tag " + (data.cv_exists ? "yes" : "no");
}

$("#settings-form").addEventListener("submit", async e => {
  e.preventDefault();
  const form = e.target;
  const payload = {};
  ["EXA_API_KEY", "APIFY_API_TOKEN", "HUNTER_API_KEY", "PROSPEO_API_KEY",
   "SENDER_EMAIL", "GMAIL_APP_PASSWORD", "CV_PATH"].forEach(k => { payload[k] = form.elements[k].value; });
  try {
    await postJSON("/api/config", payload);
    const msg = $("#settings-msg"); msg.textContent = "✓ Saved";
    setTimeout(() => (msg.textContent = ""), 2500);
    await loadSettings();
  } catch (err) { toast(err.message, true); }
});

/* ---------- Pipeline actions + job polling ---------- */
document.addEventListener("click", async e => {
  const btn = e.target.closest("[data-action]");
  if (!btn) return;
  const action = btn.dataset.action;

  if (action === "search") {
    const query = $("#search-query").value.trim();
    if (!query) { toast("Enter a search query first.", true); return; }
    const limit = parseInt($("#search-limit").value, 10) || 15;
    runAction("/api/action/search", { query, limit });
  } else if (action === "scrape") {
    runAction("/api/action/scrape", {});
  } else if (action === "generate") {
    runAction("/api/action/generate", {});
  } else if (action === "send") {
    const approved = QUEUE_CACHE.filter(r => r.status === "Approved" && r.email).length;
    confirmAction("Send real emails now?",
      `This sends live outreach emails (CV + cover letter) to up to 15 Approved companies${approved ? ` — ${approved} queued` : ""}. ` +
      `A 30–60s delay runs between each, so it may take several minutes. This cannot be undone.`,
      () => runAction("/api/action/send", {}), "Send emails");
  }
});

async function runAction(path, body) {
  try {
    await postJSON(path, body);
    $("#console").textContent = "";
    startPolling();
    toast("Job started");
  } catch (err) { toast(err.message, true); }
}

let pollTimer = null;
function startPolling() {
  stopPolling();
  pollJob();
  pollTimer = setInterval(pollJob, 1200);
}
function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } }

async function pollJob() {
  let j;
  try { j = await api("/api/job"); }
  catch (_) { return; }
  renderJob(j);
  if (j.status !== "running") {
    stopPolling();
    // Refresh whatever view might be affected.
    refreshAfterJob();
  }
}

function renderJob(j) {
  const stateEl = $("#job-state");
  const map = { idle: ["Idle", "idle"], running: ["Running…", "running"], done: ["Done", "done"], error: ["Error", "error"] };
  const [label, cls] = map[j.status] || map.idle;
  stateEl.textContent = label;
  stateEl.className = "pill " + cls;
  $("#job-name").textContent = j.name ? "· " + j.name : "";
  const con = $("#console");
  const atBottom = con.scrollHeight - con.scrollTop - con.clientHeight < 40;
  con.textContent = j.log || (j.status === "running" ? "Starting…" : "No output.");
  if (atBottom) con.scrollTop = con.scrollHeight;
  $("#job-times").textContent = j.started ? `Started ${j.started}${j.finished ? " · finished " + j.finished : ""}` : "";
}

function refreshAfterJob() {
  const active = $(".view.active");
  if (!active) return;
  const id = active.id.replace("view-", "");
  if (id === "queue") loadQueue();
  if (id === "letters") loadLetters();
  if (id === "logs") loadLogs();
  if (id === "followups") loadFollowups();
  if (id === "dashboard") loadDashboard();
  // Keep send-readiness note fresh regardless.
  api("/api/queue").then(d => { QUEUE_CACHE = d.rows; updateSendNote(); }).catch(() => {});
}

$("#console-clear").addEventListener("click", () => {
  $("#console").textContent = "Console cleared. Run an action to see live output.";
});

/* ---------- Modals ---------- */
function openModal(id) { $("#" + id).classList.remove("hidden"); }
function closeModals() { $$(".modal-overlay").forEach(m => m.classList.add("hidden")); }
document.addEventListener("click", e => {
  if (e.target.matches("[data-close-modal]") || e.target.classList.contains("modal-overlay")) closeModals();
});
document.addEventListener("keydown", e => { if (e.key === "Escape") closeModals(); });

let confirmCb = null;
function confirmAction(title, body, cb, okLabel) {
  $("#confirm-title").textContent = title;
  $("#confirm-body").textContent = body;
  $("#confirm-ok").textContent = okLabel || "Confirm";
  confirmCb = cb;
  openModal("confirm-modal");
}
$("#confirm-ok").addEventListener("click", () => {
  closeModals();
  const cb = confirmCb; confirmCb = null;
  if (cb) cb();
});

/* ---------- Boot ---------- */
(async function boot() {
  showView("dashboard");
  // Resume polling if a job is already running (e.g. after a page refresh).
  try {
    const j = await api("/api/job");
    if (j.status === "running") { showView("actions"); startPolling(); }
  } catch (_) {
    $("#conn-dot").className = "dot bad";
    $("#conn-text").textContent = "offline";
  }
})();
