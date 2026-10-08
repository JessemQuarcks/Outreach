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

