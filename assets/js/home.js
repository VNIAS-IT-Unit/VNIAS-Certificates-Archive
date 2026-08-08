/* ============================================================================
   home.js — hydrates the homepage counters from the published manifests.
   ----------------------------------------------------------------------------
   The homepage is hand-authored (see planning/07 §11): its structure is fixed and
   only the numbers come from data. Without JS the page is fully navigable and the
   counters simply read "—" rather than showing a stale hardcoded figure.
   ========================================================================= */

import { url } from "./app.js";

function animate(el, target) {
  el.dataset.count = String(target);
  const from = Number(String(el.textContent).replace(/\D/g, "")) || 0;
  // Final value first — see the note in app.js countUp().
  el.textContent = target.toLocaleString();
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const start = performance.now();
  const tick = (now) => {
    const t = Math.min((now - start) / 900, 1);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = Math.round(from + (target - from) * eased).toLocaleString();
    if (t < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

async function hydrate() {
  let stats;
  try {
    const res = await fetch(url("data/stats.json"));
    if (!res.ok) return;
    stats = await res.json();
  } catch {
    return; // offline or not yet published — the static fallbacks stand
  }

  const totals = {
    certificates: stats.certificates_total ?? 0,
    projects: stats.projects_total ?? 0,
    categories: stats.categories_total ?? 4,
    years: stats.years_covered ?? 1,
  };

  document.querySelectorAll("[data-stat]").forEach((el) => {
    const value = totals[el.dataset.stat];
    if (typeof value === "number") animate(el, value);
  });

  const byCategory = stats.by_category || {};
  document.querySelectorAll("[data-cat]").forEach((card) => {
    const entry = byCategory[card.dataset.cat];
    const el = card.querySelector(".cat-count b");
    if (entry && el) animate(el, entry.certificates ?? 0);
  });
}

hydrate();
