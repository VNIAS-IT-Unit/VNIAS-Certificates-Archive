/* ============================================================================
   certificate.js — behaviour for the certificate detail page
   ========================================================================= */

import { copy, toast, reduceMotion } from "./app.js";

/* ── Parallax tilt on the framed certificate ─────────────────────────── */

function initTilt() {
  const wrap = document.querySelector(".cert-frame-wrap");
  const frame = wrap?.querySelector(".cert-frame");
  if (!wrap || !frame) return;
  if (reduceMotion() || matchMedia("(hover: none)").matches) return;

  const MAX = 6; // degrees — beyond this it stops reading as depth and starts
                 // reading as a broken transform.

  wrap.addEventListener(
    "pointermove",
    (e) => {
      const r = wrap.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width;
      const py = (e.clientY - r.top) / r.height;
      // perspective() lives in the transform rather than on the ancestor — see
      // the note in pages.css.
      frame.style.transform =
        `perspective(1400px) rotateY(${(px - 0.5) * MAX * 2}deg) ` +
        `rotateX(${(0.5 - py) * MAX * 2}deg)`;
      frame.style.setProperty("--mx", `${px * 100}%`);
      frame.style.setProperty("--my", `${py * 100}%`);
    },
    { passive: true }
  );

  wrap.addEventListener("pointerleave", () => {
    const from = frame.style.transform;
    frame.style.transform = "";
    if (!from || typeof frame.animate !== "function") return;
    // Ease back to rest without a standing CSS transition — see pages.css.
    frame.animate([{ transform: from }, { transform: "none" }], {
      duration: 320,
      easing: "cubic-bezier(0.16, 1, 0.3, 1)",
    });
  });
}

/* ── Lightbox ────────────────────────────────────────────────────────── */

function initLightbox() {
  const img = document.querySelector(".cert-frame img");
  const dialog = document.getElementById("lightbox");
  if (!img || !dialog) return;

  const target = dialog.querySelector("img");

  const open = () => {
    target.src = img.currentSrc || img.src;
    target.alt = img.alt;
    dialog.showModal();
  };

  img.addEventListener("click", open);
  img.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      open();
    }
  });

  dialog.addEventListener("click", (e) => {
    // Clicking the backdrop (i.e. the dialog itself) dismisses.
    if (e.target === dialog || e.target.closest(".lightbox-close") || e.target === target) {
      dialog.close();
    }
  });
}

/* ── Share ───────────────────────────────────────────────────────────── */

function initShare() {
  const btn = document.querySelector("[data-share]");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    const payload = {
      title: btn.dataset.shareTitle || document.title,
      text: btn.dataset.shareText || "",
      url: location.href,
    };
    if (navigator.share) {
      try {
        await navigator.share(payload);
        return;
      } catch (err) {
        if (err?.name === "AbortError") return; // user dismissed the sheet
      }
    }
    copy(location.href, "Verification link copied");
  });
}

/* ── Print ───────────────────────────────────────────────────────────── */

function initPrint() {
  document.querySelector("[data-print]")?.addEventListener("click", () => window.print());
}

initTilt();
initLightbox();
initShare();
initPrint();

export { toast };
