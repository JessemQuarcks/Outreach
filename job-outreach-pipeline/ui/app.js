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

