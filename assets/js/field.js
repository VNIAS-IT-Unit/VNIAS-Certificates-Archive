/* ============================================================================
   field.js — constellation background
   ----------------------------------------------------------------------------
   A 2D-canvas particle field with proximity links, tinted in the two logo hues.
   Chosen over a WebGL/three.js scene deliberately: this is ~2 KB and holds 60 fps
   on a mid-range phone, where a 600 KB 3D bundle would dominate the page budget
   for a background effect. It self-disables on small screens, on reduced-motion,
   on save-data, and whenever the page is not visible.
   ========================================================================= */

const CFG = {
  density: 12000, // one particle per N px² of viewport
  max: 90,
  linkDist: 132,
  speed: 0.13,
  fps: 30,
};

/** Particle colours come from tokens.css, so the field follows the theme
    instead of hardcoding a palette that only works on a dark canvas. */
function palette() {
  const cs = getComputedStyle(document.documentElement);
  const rgb = (name, fallback) => {
    const v = cs.getPropertyValue(name).trim();
    const parts = v.split(",").map((n) => Number(n.trim()));
    return parts.length === 3 && parts.every(Number.isFinite) ? parts : fallback;
  };
  const num = (name, fallback) => {
    const v = parseFloat(cs.getPropertyValue(name));
    return Number.isFinite(v) ? v : fallback;
  };
  return {
    teal: rgb("--field-dot", [23, 168, 212]),
    lime: rgb("--field-dot-alt", [166, 201, 20]),
    alpha: num("--field-alpha", 0.6),
    link: num("--field-link-alpha", 0.18),
  };
}

function shouldRun() {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return false;
  if (innerWidth < 640) return false;
  if (navigator.connection?.saveData) return false;
  return true;
}

export function initField(canvas) {
  if (!canvas) return;

  // Conditions are re-evaluated on resize rather than only at load, so rotating
  // a phone from portrait (field off) to landscape (field on) works, and a
  // pane that reports a zero-width viewport at boot recovers once it has one.
  if (!shouldRun()) {
    let armed = true;
    addEventListener("resize", function retry() {
      if (armed && shouldRun()) {
        armed = false;
        removeEventListener("resize", retry);
        initField(canvas);
      }
    });
    return;
  }

  const ctx = canvas.getContext("2d", { alpha: true });
  if (!ctx) return;

  let dpr = 1;
  let w = 0;
  let h = 0;
  let particles = [];
  let theme = palette();
  let raf = 0;
  let last = 0;
  const pointer = { x: -9999, y: -9999 };

  const rand = (a, b) => a + Math.random() * (b - a);

  function resize() {
    dpr = Math.min(devicePixelRatio || 1, 2);
    w = canvas.clientWidth;
    h = canvas.clientHeight;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    theme = palette();
    const count = Math.min(CFG.max, Math.round((w * h) / CFG.density));
    particles = Array.from({ length: count }, () => ({
      x: rand(0, w),
      y: rand(0, h),
      vx: rand(-CFG.speed, CFG.speed),
      vy: rand(-CFG.speed, CFG.speed),
      r: rand(0.7, 2.1),
      // A minority of lime particles echoes the logo's proportions.
      hue: Math.random() < 0.22 ? theme.lime : theme.teal,
      a: rand(0.35, 1) * theme.alpha,
    }));
  }

  function step(now) {
    raf = requestAnimationFrame(step);
    if (now - last < 1000 / CFG.fps) return;
    last = now;

    ctx.clearRect(0, 0, w, h);

    for (const p of particles) {
      p.x += p.vx;
      p.y += p.vy;
      if (p.x < -20) p.x = w + 20;
      else if (p.x > w + 20) p.x = -20;
      if (p.y < -20) p.y = h + 20;
      else if (p.y > h + 20) p.y = -20;

      // Gentle repulsion from the cursor gives the field a sense of depth.
      const dx = p.x - pointer.x;
      const dy = p.y - pointer.y;
      const d2 = dx * dx + dy * dy;
      if (d2 < 16000 && d2 > 1) {
        const f = (1 - d2 / 16000) * 0.6;
        const d = Math.sqrt(d2);
        p.x += (dx / d) * f;
        p.y += (dy / d) * f;
      }

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${p.hue[0]},${p.hue[1]},${p.hue[2]},${p.a})`;
      ctx.fill();
    }

    for (let i = 0; i < particles.length; i++) {
      const a = particles[i];
      for (let j = i + 1; j < particles.length; j++) {
        const b = particles[j];
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const dist = Math.hypot(dx, dy);
        if (dist > CFG.linkDist) continue;
        const alpha = (1 - dist / CFG.linkDist) * theme.link;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = `rgba(${a.hue[0]},${a.hue[1]},${a.hue[2]},${alpha})`;
        ctx.lineWidth = 0.6;
        ctx.stroke();
      }
    }
  }

  function start() {
    if (!raf) raf = requestAnimationFrame(step);
  }
  function stop() {
    cancelAnimationFrame(raf);
    raf = 0;
  }

  resize();
  start();

  let resizeTimer;
  addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(resize, 180);
  });

  addEventListener(
    "pointermove",
    (e) => {
      pointer.x = e.clientX;
      pointer.y = e.clientY;
    },
    { passive: true }
  );
  addEventListener("pointerleave", () => {
    pointer.x = pointer.y = -9999;
  });

  // Never burn CPU in a background tab.
  document.addEventListener("visibilitychange", () => {
    document.hidden ? stop() : start();
  });
}

const canvas = document.getElementById("field");
if (canvas) initField(canvas);
