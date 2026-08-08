# VNIAS Certificate Archive & Verification Portal

The public half of the VNIAS Certificate Management System: a static, dependency-free site that
hosts every issued certificate's permanent verification page.

Full design rationale: [`../DesktopSystem/planning/07-static-website.md`](../DesktopSystem/planning/07-static-website.md).

---

## Quick start

```bash
uv run --with pillow --with segno python tools/build_site.py --demo --clean
```

```bash
python -m http.server 8899
```

Then open <http://127.0.0.1:8899/>.

| Command | Effect |
|---------|--------|
| `--demo` | seeds 8 programmes / 170 certificates with rendered artwork and real QR codes |
| `--clean` | deletes generated output first (`data/`, `verify/<category>/`, `certificates/`, `media/`) |
| *(no flags)* | rebuilds pages and manifests from an empty dataset — the production shape, before the desktop app publishes anything |

The demo dataset is deterministic (fixed RNG seed), so rebuilding produces byte-identical output and
no spurious git churn.

---

## Layout

```
index.html  verify/index.html  about/index.html  404.html   ← hand-authored shell
assets/css/{tokens,base,components,pages}.css               ← design system
assets/js/{app,field,search,certificate,home}.js            ← ES modules, no dependencies
assets/brand/                                               ← logo derivatives, favicons, OG card, sprite
tools/build_site.py                                         ← generator (prototype of the desktop service)
tools/demo_data.py                                          ← demo corpus + certificate/QR rendering

── generated ──────────────────────────────────────────────
verify/<category>/index.html                                ← category listing
verify/<category>/<slug>/index.html                         ← programme + certificate roll
verify/<category>/<slug>/<CERT-ID>/index.html               ← certificate detail page
certificates/<category>/<slug>/<CERT-ID>.webp               ← web-optimised certificate
media/<category>/<slug>/{poster,cover,banner}-{400,800,1600}.webp
data/site.json · stats.json · categories/*.json · projects/**/*.json · registry/<year>-<category>.json
sitemap.xml · robots.txt · .nojekyll
```

**The seam:** the shell is hand-authored and rarely changes; everything under `verify/<category>/`,
`certificates/`, `media/` and `data/` is generated. The desktop application will own the generated
half via Jinja2 templates that reuse these exact CSS class names and JSON schemas.

---

## Architecture notes

**No framework and no build step.** Pages are produced by the desktop app on a non-technical
operator's Windows machine; a Node/npm toolchain there is not acceptable. Everything here runs as
authored.

**IDs route themselves.** `VNIAS-WS-26-7F3KQ2M9XB` names its own registry shard
(`data/registry/2026-workshop.json`), so a lookup fetches exactly one small file no matter how many
certificates exist. Lookup cost is independent of archive size.

**Suspension is not deletion.** A suspended certificate keeps its page (HTTP 200), keeps its ID
forever, loses its image from the repository, and states the suspension. A verification link that
once resolved must never start 404-ing.

**No participant PII is ever published.** Manifests and pages carry only what is printed on the face
of the certificate — name, programme, dates. The generator has no code path that emits an email
address, and the build asserts it.

**Content never depends on JavaScript to be visible.** Reveal animations are scoped to a `.js` class
set by an inline script; with JS disabled the page renders fully, just without motion.

---

## Verified behaviour

Checked against the running demo build:

| Check | Result |
|-------|--------|
| Certificate page resolves from registry lookup | 200, ID matches, image 200, JSON-LD present |
| ID input tolerance — lowercase, spaces, no dashes, padding, O/I confusables | all 5 resolve |
| Unknown ID / wrong programme code / wrong year | reported `unknown`, not a crash |
| Non-ID garbage input | reported `malformed` with format guidance |
| Suspended certificate | page 200 · verdict "Suspended" · image withdrawn (404) · `noindex` |
| PII guard | no `@` in project manifests; no email in certificate pages |
| Every page | exactly one `h1`, all `<use>` refs resolve, every `img` has `alt` + explicit dimensions |
| Horizontal overflow at 1440 px | none |
| Sitemap | 184 URLs; the suspended certificate is correctly excluded |

Visual pass in Chrome at 1440 px found and fixed four real defects:

1. **The lightbox `<dialog>` rendered open on every certificate page**, covering the whole record —
   `display: grid` on the base selector overrode the UA's `dialog:not([open]) { display: none }`.
   The display switch is now keyed to `[open]`.
2. **The verification seal had no icon** — `.seal::after` is the last child and painted its solid
   disc straight over the glyph. Fixed with `z-index` on the icon.
3. **Non-ASCII characters were double-encoded** in the four hand-authored pages after a PowerShell
   rewrite (PS 5.1 reads UTF-8 as ANSI by default). 23 characters repaired; these files are only
   ever edited with UTF-8-aware tools now.
4. **A reveal transition frozen by a hidden tab could strand content part-faded.** Chrome stops the
   animation timeline for a backgrounded document, so `transitionend` never fires. The reveal now
   settles on a timer that also cancels the in-flight transition, so content cannot depend on an
   animation completing.

**Theme:** the portal ships **light**. The dark set is retained under `[data-theme="dark"]` as the
desktop-application mirror and is opt-in only.

**Payload** (uncompressed → typical gzip on GitHub Pages):
CSS 42.9 KB → ~11 KB · JS 20.9 KB → ~6 KB · certificate page 17.8 KB → ~4.5 KB · certificate
image ~61 KB (demo artwork; real photographic templates will be 120–220 KB).

About 4.5 KB of each page is the inlined icon sprite. It is inlined rather than referenced because
Safari still does not resolve `<use href="external.svg#id">`; the cost buys correctness in every
browser and one fewer request.

**Not yet verified:** appearance below 1440 px. Window resizing did not take effect in the automation
browser, so the 375 / 768 breakpoints have been validated structurally (no fixed widths, fluid
`clamp()` type, `auto-fit` grids, `.roll-id` hidden under 560 px, nav collapsing under 760 px) but not
seen. Worth a look on a real phone before launch.

**A note on screenshots.** Chrome freezes the animation timeline and stops repainting when its window
is hidden or occluded. In that state elements sit part-way through their reveal transition and images
that decoded after first paint never appear, so captures show blank regions that are not real
defects. If you are reviewing screenshots, keep the browser window visible and in the foreground.

---

## Deployment

Push the whole directory to the certificate repository's GitHub Pages branch. `.nojekyll` is present
and matters: with tens of thousands of files, Jekyll processing is the difference between a
40-second and a nine-minute build.

Before going live: set the real site URL in `tools/build_site.py` (`SITE_URL`), add a `CNAME` file if
serving from a custom domain, and replace the `DEVELOPER["linkedin"]` placeholder.
