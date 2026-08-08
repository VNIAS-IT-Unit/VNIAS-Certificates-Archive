/* ============================================================================
   app.js — shared behaviour for every page
   Zero dependencies. All paths resolve against <html data-base="...">, so the
   site works from a domain root, a GitHub Pages sub-path or the filesystem.
   ========================================================================= */

export const BASE = document.documentElement.dataset.base || "./";
export const url = (path) => BASE + String(path).replace(/^\/+/, "");

export const reduceMotion = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ── Header ──────────────────────────────────────────────────────────── */

function initHeader() {
  const header = document.querySelector(".site-header");
  if (!header) return;

  const onScroll = () => header.classList.toggle("is-stuck", window.scrollY > 8);
  onScroll();
  addEventListener("scroll", onScroll, { passive: true });

  const toggle = header.querySelector(".nav-toggle");
  const nav = header.querySelector(".site-nav");
  if (!toggle || !nav) return;

  toggle.addEventListener("click", () => {
    const open = nav.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", String(open));
  });
  nav.addEventListener("click", (e) => {
    if (e.target.closest("a")) {
      nav.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
    }
  });
}

/* ── Scroll reveal ───────────────────────────────────────────────────── */

/**
 * Clear the reveal state once the entrance is done — by transitionend if it
 * fires, and unconditionally by timer if it does not.
 *
 * The timer is not belt-and-braces, it is the actual guarantee. A reveal
 * transition was observed stalling part-way under software compositing, so
 * `transitionend` never fired and the element stayed part-faded and stuck on
 * its own layer. Content must never depend on an animation reaching its end
 * state.
 */
function settle(el, delay) {
  const done = () => {
    // Suppress the transition before dropping the attribute, so an in-flight
    // interpolation cannot keep governing the computed value. This is what makes
    // the background-tab case safe: Chrome freezes the animation timeline for a
    // hidden document, which would otherwise strand the element part-faded until
    // the user focused the tab again.
    el.style.transition = "none";
    el.removeAttribute("data-reveal");
    el.style.removeProperty("--reveal-delay");
    void el.offsetHeight; // flush the style change before restoring transitions
    el.style.removeProperty("transition");
  };
  el.addEventListener("transitionend", done, { once: true });
  setTimeout(done, delay + 900);
}

function initReveal() {
  const items = document.querySelectorAll("[data-reveal]");
  if (!items.length) return;

  if (reduceMotion() || !("IntersectionObserver" in window)) {
    items.forEach((el) => el.classList.add("is-visible"));
    return;
  }

  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        // Stagger siblings so a grid resolves as a wave, not a flash.
        const group = entry.target.parentElement;
        const index = group ? [...group.children].indexOf(entry.target) : 0;
        entry.target.style.setProperty("--reveal-delay", `${Math.min(index, 8) * 55}ms`);
        entry.target.classList.add("is-visible");
        io.unobserve(entry.target);

        settle(entry.target, Math.min(index, 8) * 55);
      });
    },
    { rootMargin: "0px 0px -8% 0px", threshold: 0.08 }
  );

  items.forEach((el) => io.observe(el));
}

/* ── Animated counters ───────────────────────────────────────────────── */

function countUp(el) {
  const target = Number(el.dataset.count || 0);
  // Write the real value first, then animate over it. If requestAnimationFrame
  // never runs — background tab, throttled renderer — the correct number is
  // already on screen rather than a placeholder frozen forever.
  el.textContent = target.toLocaleString();
  if (reduceMotion() || target === 0) return;

  const duration = 1100;
  const start = performance.now();
  const tick = (now) => {
    const t = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = Math.round(target * eased).toLocaleString();
    if (t < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function initCounters() {
  const els = document.querySelectorAll("[data-count]");
  if (!els.length) return;
  if (!("IntersectionObserver" in window)) return els.forEach(countUp);

  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        countUp(e.target);
        io.unobserve(e.target);
      });
    },
    { threshold: 0.4 }
  );
  els.forEach((el) => io.observe(el));
}

/* ── Pointer-tracked sheen on cards ──────────────────────────────────── */

function initSheen() {
  if (reduceMotion() || matchMedia("(hover: none)").matches) return;

  const track = (e) => {
    const el = e.currentTarget;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${((e.clientX - r.left) / r.width) * 100}%`);
    el.style.setProperty("--my", `${((e.clientY - r.top) / r.height) * 100}%`);
  };

  document.querySelectorAll(".card, .cat-card").forEach((el) => {
    el.addEventListener("pointermove", track, { passive: true });
  });
}

/* ── Toast + clipboard ───────────────────────────────────────────────── */

export function toast(message) {
  let host = document.querySelector(".toast-host");
  if (!host) {
    host = document.createElement("div");
    host.className = "toast-host";
    host.setAttribute("role", "status");
    host.setAttribute("aria-live", "polite");
    document.body.append(host);
  }
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = message;
  host.append(el);
  setTimeout(() => el.remove(), 2600);
}

export async function copy(text, message = "Copied to clipboard") {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // Clipboard API needs a secure context; this fallback keeps file:// working.
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.cssText = "position:fixed;opacity:0";
    document.body.append(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
  toast(message);
}

function initCopyButtons() {
  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", () => copy(btn.dataset.copy));
  });
}

/* ── Boot ────────────────────────────────────────────────────────────── */

function boot() {
  initHeader();
  initReveal();
  initCounters();
  initSheen();
  initCopyButtons();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot, { once: true });
} else {
  boot();
}
