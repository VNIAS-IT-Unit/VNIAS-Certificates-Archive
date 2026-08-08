/* ============================================================================
   search.js — certificate ID lookup
   ----------------------------------------------------------------------------
   IDs carry their own routing information: VNIAS-<CAT>-<YY>-<BODY>. The category
   code and year name the registry shard, so a lookup fetches exactly one small
   file regardless of how many certificates exist in total. That property is what
   lets this scale past six figures without a search backend.
   ========================================================================= */

import { url, toast } from "./app.js";

const ID_RE = /^VNIAS-([A-Z]{2})-(\d{2})-([0-9A-Z]{6,16})$/;

/**
 * Accepts anything a human might type or paste — lowercase, spaces instead of
 * dashes, no separators at all, or Crockford confusables ("O" for zero, "I"/"L"
 * for one) — and returns the canonical form.
 *
 * The confusable mapping is applied ONLY to the year and the random body. The
 * literal "VNIAS" prefix and the two-letter programme code are fixed vocabulary:
 * rewriting them turns VNIAS into VN1AS and every lookup fails.
 */
function normalize(raw) {
  const compact = String(raw).toUpperCase().replace(/[^0-9A-Z]/g, "");
  if (!compact.startsWith("VNIAS")) return compact;

  const digits = (s) => s.replace(/[IL]/g, "1").replace(/O/g, "0");
  const code = compact.slice(5, 7);
  const year = digits(compact.slice(7, 9));
  const body = digits(compact.slice(9));
  return `VNIAS-${code}-${year}-${body}`;
}

let siteCache = null;
async function site() {
  if (!siteCache) {
    const res = await fetch(url("data/site.json"));
    if (!res.ok) throw new Error("site-unavailable");
    siteCache = await res.json();
  }
  return siteCache;
}

const shardCache = new Map();
async function shard(year, category) {
  const key = `${year}-${category}`;
  if (!shardCache.has(key)) {
    const res = await fetch(url(`data/registry/${key}.json`));
    shardCache.set(key, res.ok ? await res.json() : null);
  }
  return shardCache.get(key);
}

/**
 * @returns {Promise<{status:'found'|'unknown'|'malformed'|'error', id?:string, path?:string}>}
 */
export async function lookup(raw) {
  const id = normalize(raw);
  const m = ID_RE.exec(id);
  if (!m) return { status: "malformed", id };

  const [, code, yy] = m;
  try {
    const cfg = await site();
    const category = cfg.categories.find((c) => c.id_code === code);
    if (!category) return { status: "unknown", id };

    const table = await shard(`20${yy}`, category.key);
    const path = table?.[id];
    return path ? { status: "found", id, path } : { status: "unknown", id };
  } catch {
    return { status: "error", id };
  }
}

/* ── Wiring ──────────────────────────────────────────────────────────── */

const MESSAGES = {
  malformed:
    'That does not look like a VNIAS certificate ID. IDs are formatted <code>VNIAS-WS-26-7F3KQ2M9XB</code>.',
  unknown:
    "No certificate with that ID has been issued by VNIAS. Check the ID against the printed certificate, or contact us if you believe this is an error.",
  error:
    "The certificate registry could not be reached. Please check your connection and try again.",
};

function setStatus(box, kind, html) {
  if (!box) return;
  box.hidden = false;
  box.className = `search-status search-status--${kind}`;
  box.innerHTML = html;
}

function initSearchForms() {
  document.querySelectorAll("form[data-search]").forEach((form) => {
    const input = form.querySelector("input");
    const box = document.querySelector(form.dataset.search || ".search-status");
    const button = form.querySelector("button[type=submit]");

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const raw = input.value.trim();
      if (!raw) {
        input.focus();
        return;
      }

      button?.setAttribute("disabled", "");
      setStatus(box, "pending", "Checking the registry…");

      const result = await lookup(raw);
      button?.removeAttribute("disabled");

      if (result.status === "found") {
        setStatus(box, "ok", `Certificate <code>${result.id}</code> found. Opening…`);
        remember(result.id);
        location.href = url(result.path);
        return;
      }
      setStatus(box, "error", MESSAGES[result.status]);
    });
  });
}

/* ── Recent lookups (local only, never transmitted) ──────────────────── */

const KEY = "vnias.recent";

function remember(id) {
  try {
    const list = JSON.parse(localStorage.getItem(KEY) || "[]");
    const next = [id, ...list.filter((x) => x !== id)].slice(0, 5);
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* private mode — recents are a convenience, not a requirement */
  }
}

function initRecent() {
  const host = document.querySelector("[data-recent]");
  if (!host) return;
  let list = [];
  try {
    list = JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch {
    return;
  }
  if (!list.length) return;

  host.hidden = false;
  host.innerHTML =
    '<span class="search-hint">Recent lookups</span> ' +
    list.map((id) => `<button class="chip" type="button" data-id="${id}">${id}</button>`).join("");

  host.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-id]");
    if (!btn) return;
    const input = document.querySelector("form[data-search] input");
    if (input) {
      input.value = btn.dataset.id;
      input.form.requestSubmit();
    }
  });
}

/** Deep link support: /verify/?id=VNIAS-WS-26-… */
function initQueryLookup() {
  const q = new URLSearchParams(location.search).get("id");
  if (!q) return;
  const input = document.querySelector("form[data-search] input");
  if (!input) return;
  input.value = q;
  input.form.requestSubmit();
}

initSearchForms();
initRecent();
initQueryLookup();

export { toast };
