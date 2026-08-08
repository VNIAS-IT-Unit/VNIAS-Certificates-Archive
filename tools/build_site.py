"""
VNIAS Certificate Archive — static site generator (reference implementation).

This script is the executable specification of the data contract described in
planning/07-static-website.md §6. The desktop application will port it to
Jinja2 templates inside `services/publishing/site_generator.py`; keeping a
runnable version here means the website can be built, reviewed and tested long
before the desktop app exists, and any change that breaks the contract breaks
this script first.

It does four things:

  1. seeds a realistic demo dataset (opt-in via --demo)
  2. writes the JSON manifests the site reads
  3. renders every generated HTML page (category, project, certificate)
  4. inlines the shared icon sprite into every page, hand-authored ones included

Run:  uv run --with pillow --with segno python tools/build_site.py --demo
"""

from __future__ import annotations

import argparse
import html
import json
import random
import re
import shutil
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
DATA = ROOT / "data"
VERIFY = ROOT / "verify"
CERTS = ROOT / "certificates"
MEDIA = ROOT / "media"

SITE_URL = "https://vnias.org"
ORG = "VitaNova International Alliance for Sciences"
CONTACT = "vitanova.science@gmail.com"
DEVELOPER = {"name": "Syed Shahzil", "linkedin": "https://www.linkedin.com/in/syedshahzil/"}

# Crockford Base32 — no I, L, O or U, so identifiers survive being read aloud.
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

# Categories are data, not code — this list is the website's mirror of the
# `categories` table in the desktop application. Adding one adds a board, a
# route, an ID code and a colour, with no other change anywhere.
CATEGORIES = [
    {"key": "event", "label_singular": "Event", "label_plural": "Events",
     "url_segment": "events", "id_code": "EV", "icon": "i-calendar",
     "accent": "var(--cat-event)", "hex": "#17a8d4", "sort_order": 1,
     "blurb": "Summits, conferences and international gatherings hosted or co-hosted by VNIAS."},
    {"key": "session", "label_singular": "Session", "label_plural": "Sessions",
     "url_segment": "sessions", "id_code": "SE", "icon": "i-mic",
     "accent": "var(--cat-session)", "hex": "#37c0c8", "sort_order": 2,
     "blurb": "Seminars, webinars and guest lectures delivered by researchers and practitioners."},
    {"key": "workshop", "label_singular": "Workshop", "label_plural": "Workshops",
     "url_segment": "workshops", "id_code": "WS", "icon": "i-board",
     "accent": "var(--cat-workshop)", "hex": "#6bc46a", "sort_order": 3,
     "blurb": "Hands-on training in laboratory technique, bioinformatics and scientific computing."},
    {"key": "course", "label_singular": "Course", "label_plural": "Courses",
     "url_segment": "courses", "id_code": "CO", "icon": "i-book",
     "accent": "var(--cat-course)", "hex": "#a6c914", "sort_order": 4,
     "blurb": "Multi-week structured programmes with assessment and a certificate of completion."},
]

BY_KEY = {c["key"]: c for c in CATEGORIES}


# ═══════════════════════════════════════════════════════════════════════════
# Domain model — mirrors core/models in the desktop application
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Person:
    name: str
    role: str
    title: str = ""
    affiliation: str = ""
    profile_url: str = ""


@dataclass
class Certificate:
    id: str
    name: str
    status: str = "verified"           # verified | suspended
    suspended_on: str = ""
    suspended_note: str = ""


@dataclass
class Project:
    category: str
    slug: str
    title: str
    subtitle: str
    description: str
    event_date: str
    event_end_date: str
    issue_date: str
    mode: str                          # in_person | online | hybrid
    venue: str
    platform: str
    notes: str = ""
    people: list[Person] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    certificates: list[Certificate] = field(default_factory=list)

    @property
    def path(self) -> str:
        return f"verify/{BY_KEY[self.category]['url_segment']}/{self.slug}/"


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return re.sub(r"-{2,}", "-", text)[:60]


def make_id(code: str, year: int, rng: random.Random) -> str:
    body = "".join(rng.choice(ALPHABET) for _ in range(10))
    return f"VNIAS-{code}-{year % 100:02d}-{body}"


def e(text) -> str:
    return html.escape(str(text or ""), quote=True)


def fmt_date(iso: str) -> str:
    if not iso:
        return ""
    y, m, d = (int(p) for p in iso.split("-"))
    months = ("January February March April May June July August September "
              "October November December").split()
    return f"{d} {months[m - 1]} {y}"


def initials(name: str) -> str:
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # sort_keys keeps republished files byte-identical when nothing changed,
    # so git diffs stay meaningful across thousands of certificates.
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def write_html(path: Path, markup: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markup, encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# Shared page chrome
# ═══════════════════════════════════════════════════════════════════════════

def head(*, base: str, title: str, description: str, canonical: str,
         og_image: str, noindex: bool = False, extra: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en" data-base="{base}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>document.documentElement.classList.add("js")</script>
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{e(canonical)}">
<meta name="theme-color" content="#eaf1f5">
{'<meta name="robots" content="noindex">' if noindex else ''}
<meta property="og:type" content="website">
<meta property="og:site_name" content="VNIAS Certificate Archive">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{e(canonical)}">
<meta property="og:image" content="{e(og_image)}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{base}assets/brand/favicon.ico" sizes="any">
<link rel="icon" type="image/png" href="{base}assets/brand/favicon-32.png">
<link rel="apple-touch-icon" href="{base}assets/brand/favicon-180.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&amp;family=JetBrains+Mono:wght@500;600&amp;family=Poppins:wght@600;700&amp;display=swap">
<link rel="stylesheet" href="{base}assets/css/tokens.css">
<link rel="stylesheet" href="{base}assets/css/base.css">
<link rel="stylesheet" href="{base}assets/css/components.css">
<link rel="stylesheet" href="{base}assets/css/pages.css">
{extra}
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
<div class="atmosphere" aria-hidden="true"><div class="mesh"></div><div class="bloom"></div><canvas id="field"></canvas></div>
<!--#include sprite-->
"""


def header(base: str, current: str = "") -> str:
    def mark(name: str) -> str:
        return ' aria-current="page"' if current == name else ""

    return f"""<header class="site-header">
  <div class="shell">
    <a class="brand" href="{base}">
      <img src="{base}assets/brand/vnias-mark.png" alt="" width="38" height="38">
      <span class="brand-text"><span class="brand-name">VITANOVA</span><span class="brand-sub">Certificate Archive</span></span>
    </a>
    <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="nav" aria-label="Menu">
      <svg viewBox="0 0 24 24" width="22" height="22"><use href="#i-menu"/></svg>
    </button>
    <nav class="site-nav" id="nav" aria-label="Main">
      <a href="{base}"{mark('home')}>Home</a>
      <a href="{base}verify/"{mark('verify')}>Verify</a>
      <a href="{base}verify/workshops/"{mark('archive')}>Archive</a>
      <a href="{base}about/"{mark('about')}>About</a>
      <a href="https://vnias.org" rel="noopener">vnias.org</a>
    </nav>
  </div>
</header>
"""


def footer(base: str, scripts: str = "") -> str:
    return f"""<footer class="site-footer">
  <div class="shell">
    <div class="footer-grid">
      <div class="footer-col">
        <a class="brand" href="{base}" style="margin-bottom:var(--sp-4)">
          <img src="{base}assets/brand/vnias-mark.png" alt="" width="38" height="38">
          <span class="brand-text"><span class="brand-name">VITANOVA</span><span class="brand-sub">International Alliance for Sciences</span></span>
        </a>
        <p style="font-size:var(--fs-sm);color:var(--text-3);max-width:42ch">
          A non-profit scientific council supporting students and researchers in the life sciences
          and information technology.
        </p>
      </div>
      <div class="footer-col">
        <h4>Archive</h4>
        <ul>
          <li><a href="{base}verify/events/">Events</a></li>
          <li><a href="{base}verify/sessions/">Sessions</a></li>
          <li><a href="{base}verify/workshops/">Workshops</a></li>
          <li><a href="{base}verify/courses/">Courses</a></li>
        </ul>
      </div>
      <div class="footer-col">
        <h4>Verification</h4>
        <ul>
          <li><a href="{base}verify/">Verify a certificate</a></li>
          <li><a href="{base}about/">About this archive</a></li>
          <li><a href="mailto:{CONTACT}">Report a problem</a></li>
          <li><a href="https://vnias.org" rel="noopener">Main website</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <span>&copy; <span id="year">{date.today().year}</span> {ORG}. All rights reserved.</span>
      <span class="developed-by">Developed by
        <a href="{DEVELOPER['linkedin']}" rel="noopener" target="_blank">
          <svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-linkedin"/></svg>
          {e(DEVELOPER['name'])}
        </a>
      </span>
    </div>
  </div>
</footer>
<script type="module" src="{base}assets/js/app.js"></script>
<script type="module" src="{base}assets/js/field.js"></script>
{scripts}<script>document.getElementById("year").textContent = new Date().getFullYear();</script>
</body>
</html>
"""


def crumbs(items: list[tuple[str, str]]) -> str:
    parts = []
    for label, href in items[:-1]:
        parts.append(f'<li><a href="{href}">{e(label)}</a></li>')
    parts.append(f'<li aria-current="page">{e(items[-1][0])}</li>')
    return f'<ol class="crumbs">{"".join(parts)}</ol>'


# ═══════════════════════════════════════════════════════════════════════════
# Page renderers
# ═══════════════════════════════════════════════════════════════════════════

def render_category_page(cat: dict, projects: list[Project]) -> str:
    base = "../../"
    total_certs = sum(len(p.certificates) for p in projects)

    if projects:
        cards = []
        for p in projects:
            poster = f"{base}media/{cat['url_segment']}/{p.slug}/poster-800.webp"
            cards.append(f"""      <a class="card" href="{p.slug}/" data-reveal>
        <div class="card-media">
          <img src="{poster}" alt="" width="800" height="450" loading="lazy" decoding="async">
          <span class="chip chip--accent"><span class="dot"></span>{e(cat['label_singular'])}</span>
        </div>
        <div class="card-body">
          <h3 class="card-title">{e(p.title)}</h3>
          <p class="card-sub">{e(p.subtitle)}</p>
          <div class="card-meta">
            <span><strong>{len(p.certificates)}</strong> certificates</span>
            <span>{e(fmt_date(p.event_date))}</span>
          </div>
        </div>
      </a>""")
        body = f'<div class="card-grid">\n{chr(10).join(cards)}\n    </div>'
    else:
        body = f"""<div class="empty">
        <svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-award"/></svg>
        <p>No {cat['label_plural'].lower()} have been published yet.</p>
        <a class="btn btn--ghost btn--sm" href="{base}verify/">Verify a certificate by ID</a>
      </div>"""

    return (
        head(base=base,
             title=f"{cat['label_plural']} — VNIAS Certificate Archive",
             description=f"{cat['blurb']} Browse every VNIAS {cat['label_singular'].lower()} and verify its certificates.",
             canonical=f"{SITE_URL}/verify/{cat['url_segment']}/",
             og_image=f"{SITE_URL}/assets/brand/og-default.png")
        + header(base, "archive")
        + f"""<main id="main">
  <div class="shell">
    <div class="page-head">
      {crumbs([("Archive", base), ("Verify", base + "verify/"), (cat['label_plural'], "")])}
      <span class="overline">{e(cat['label_plural'])}</span>
      <h1 style="margin-top:var(--sp-3)">{e(cat['label_plural'])} archive</h1>
      <p class="lede">{e(cat['blurb'])}</p>
      <div class="cluster" style="margin-top:var(--sp-6)">
        <span class="chip"><b style="color:var(--text-1)">{len(projects)}</b>&nbsp;programmes</span>
        <span class="chip"><b style="color:var(--text-1)">{total_certs}</b>&nbsp;certificates</span>
      </div>
    </div>
    <div class="section--tight">
      {body}
    </div>
  </div>
</main>
"""
        + footer(base)
    )


def render_project_page(cat: dict, p: Project) -> str:
    base = "../../../"
    prefix = f"{base}media/{cat['url_segment']}/{p.slug}/"

    people_html = ""
    if p.people:
        groups: dict[str, list[Person]] = {}
        for person in p.people:
            groups.setdefault(person.role, []).append(person)
        blocks = []
        for role, members in groups.items():
            cards = "".join(
                f"""<div class="person">
              <div class="person-avatar">{e(initials(m.name))}</div>
              <div><div class="person-name">{e(m.name)}</div>
              <div class="person-role">{e(m.title or m.affiliation)}</div></div>
            </div>""" for m in members)
            blocks.append(f"""      <section class="cert-section" data-reveal>
        <h2>{e(role.title())}s</h2>
        <div class="people">{cards}</div>
      </section>""")
        people_html = "\n".join(blocks)

    rows = "".join(
        f"""<a class="roll-item" href="{c.id}/">
          <span class="idx">{i + 1}</span>
          <span class="roll-name">{e(c.name)}</span>
          <span class="roll-id">{e(c.id)}</span>
        </a>""" for i, c in enumerate(p.certificates))

    where = p.venue if p.mode != "online" else p.platform
    facts = [
        ("i-calendar", fmt_date(p.event_date)),
        ("i-pin", where),
        ("i-users", f"{len(p.certificates)} participants"),
        ("i-award", f"Issued {fmt_date(p.issue_date)}"),
    ]
    facts_html = "".join(
        f'<span><svg viewBox="0 0 24 24" aria-hidden="true"><use href="#{icon}"/></svg>{e(text)}</span>'
        for icon, text in facts if text)

    return (
        head(base=base,
             title=f"{p.title} — VNIAS Certificate Archive",
             description=p.subtitle or p.description[:180],
             canonical=f"{SITE_URL}/{p.path}",
             og_image=f"{SITE_URL}/media/{cat['url_segment']}/{p.slug}/banner-1600.webp")
        + header(base, "archive")
        + f"""<main id="main">
  <div class="shell">
    <div class="page-head" style="padding-bottom:var(--sp-6)">
      {crumbs([("Archive", base), (cat['label_plural'], base + 'verify/' + cat['url_segment'] + '/'), (p.title, "")])}
    </div>

    <div class="project-hero" data-reveal>
      <div class="project-hero-media">
        <img src="{prefix}banner-1600.webp" alt="" width="1600" height="600" fetchpriority="high" decoding="async">
      </div>
      <div class="project-hero-body">
        <span class="chip chip--accent"><span class="dot"></span>{e(cat['label_singular'])}</span>
        <h1>{e(p.title)}</h1>
        <p class="sub">{e(p.subtitle)}</p>
        <div class="project-facts">{facts_html}</div>
      </div>
    </div>

    <div class="cert-sections">
      <section class="cert-section" data-reveal>
        <h2>About this {e(cat['label_singular'].lower())}</h2>
        <div class="prose"><p>{e(p.description)}</p></div>
      </section>

{people_html}

      <section class="cert-section" data-reveal>
        <h2>Certificates awarded &nbsp;<span style="color:var(--text-3);font-weight:400">{len(p.certificates)}</span></h2>
        <div class="roll">{rows}</div>
      </section>
    </div>
  </div>
</main>
"""
        + footer(base)
    )


def render_certificate_page(cat: dict, p: Project, c: Certificate) -> str:
    base = "../../../../"
    canonical = f"{SITE_URL}/{p.path}{c.id}/"
    image = f"{base}certificates/{cat['url_segment']}/{p.slug}/{c.id}.webp"
    suspended = c.status == "suspended"

    jsonld = {
        "@context": "https://schema.org",
        "@type": "EducationalOccupationalCredential",
        "name": f"{cat['label_singular']} certificate — {p.title}",
        "identifier": c.id,
        "credentialCategory": cat["label_singular"],
        "dateCreated": p.issue_date,
        "url": canonical,
        "recognizedBy": {"@type": "Organization", "name": ORG, "url": SITE_URL},
        "about": {"@type": "Event", "name": p.title, "startDate": p.event_date},
    }
    if not suspended:
        jsonld["credentialStatus"] = "Valid"

    extra = (f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>'
             f'\n<link rel="preload" as="image" href="{image}" fetchpriority="high">'
             if not suspended else
             f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>')

    if suspended:
        verdict = f"""<div class="verdict verdict--suspended" data-reveal>
        <div class="seal seal--suspended">
          <svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-alert"/></svg>
        </div>
        <div>
          <h2>Suspended</h2>
          <p>This certificate has been suspended by VNIAS and is no longer valid.</p>
        </div>
      </div>"""
        visual = f"""<div class="cert-frame">
          <div class="suspended-notice">
            <div class="seal seal--suspended" style="width:64px;height:64px">
              <svg viewBox="0 0 24 24" aria-hidden="true" style="width:28px;height:28px"><use href="#i-alert"/></svg>
            </div>
            <h2>This certificate has been suspended by VNIAS</h2>
            <p>The certificate image has been withdrawn from publication. This record remains online
               permanently so that the identifier can always be checked.</p>
            <p style="color:var(--text-disabled)">Suspended on {e(fmt_date(c.suspended_on))}</p>
          </div>
        </div>"""
        actions = f"""<a class="btn btn--ghost" href="{base}verify/">
          <svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-search"/></svg> Verify another ID</a>
        <button class="btn btn--ghost" type="button" data-share
          data-share-title="VNIAS certificate {e(c.id)}">
          <svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-share"/></svg> Share record</button>"""
        status_chip = '<span class="chip chip--suspended"><span class="dot"></span>Suspended</span>'
    else:
        verdict = f"""<div class="verdict" data-reveal>
        <div class="seal">
          <svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-shield"/></svg>
        </div>
        <div>
          <h2>Verified</h2>
          <p>This certificate was issued by {e(ORG)} and is valid.</p>
        </div>
      </div>"""
        visual = f"""<div class="cert-frame">
          <span class="sheen" aria-hidden="true"></span>
          <img src="{image}" alt="Certificate awarded to {e(c.name)} for {e(p.title)}"
               width="1600" height="1131" tabindex="0" fetchpriority="high" decoding="sync">
        </div>"""
        actions = f"""<a class="btn btn--primary" href="{image}" download="{e(c.id)}-{slugify(c.name)}.webp">
          <svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-download"/></svg> Download</a>
        <button class="btn btn--ghost" type="button" data-share
          data-share-title="VNIAS certificate — {e(c.name)}"
          data-share-text="Verified certificate {e(c.id)} issued by VNIAS">
          <svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-share"/></svg> Share</button>
        <button class="btn btn--ghost" type="button" data-print>
          <svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-print"/></svg> Print record</button>"""
        status_chip = '<span class="chip chip--verified"><span class="dot"></span>Verified</span>'

    where = p.venue if p.mode != "online" else p.platform
    meta_rows = [
        ("Certificate ID", f'<span class="mono">{e(c.id)}</span>'),
        ("Programme", e(cat["label_singular"])),
        ("Event date", e(fmt_date(p.event_date))),
        ("Issued on", e(fmt_date(p.issue_date))),
        ("Delivery", e({"in_person": "In person", "online": "Online", "hybrid": "Hybrid"}.get(p.mode, p.mode))),
        (("Venue" if p.mode != "online" else "Platform"), e(where)),
        ("Status", status_chip),
    ]
    if suspended:
        meta_rows.append(("Suspended on", e(fmt_date(c.suspended_on))))

    meta_html = "".join(
        f'<div class="meta-row"><dt>{label}</dt><dd class="{"mono" if "mono" in value else ""}">{value}</dd></div>'
        for label, value in meta_rows)

    people_html = ""
    if p.people:
        groups: dict[str, list[Person]] = {}
        for person in p.people:
            groups.setdefault(person.role, []).append(person)
        blocks = []
        for role, members in groups.items():
            cards = "".join(
                f"""<div class="person">
                <div class="person-avatar">{e(initials(m.name))}</div>
                <div><div class="person-name">{e(m.name)}</div>
                <div class="person-role">{e(m.title or m.affiliation)}</div></div>
              </div>""" for m in members)
            blocks.append(f"""        <section class="cert-section" data-reveal>
          <h2>{e(role.title())}s</h2>
          <div class="people">{cards}</div>
        </section>""")
        people_html = "\n".join(blocks)

    return (
        head(base=base,
             title=f"{c.name} — {p.title} | VNIAS Certificate {c.id}",
             description=(f"Certificate {c.id} awarded to {c.name} for {p.title}, issued by {ORG}."
                          if not suspended else
                          f"Certificate {c.id} has been suspended by {ORG}."),
             canonical=canonical,
             og_image=(f"{SITE_URL}/certificates/{cat['url_segment']}/{p.slug}/{c.id}.webp"
                       if not suspended else f"{SITE_URL}/assets/brand/og-default.png"),
             noindex=suspended,
             extra=extra)
        + header(base)
        + f"""<main id="main">
  <div class="shell shell--wide">
    <div class="page-head" style="padding-bottom:var(--sp-6)">
      {crumbs([("Archive", base),
               (cat['label_plural'], base + 'verify/' + cat['url_segment'] + '/'),
               (p.title, base + p.path),
               (c.id, "")])}
    </div>

    <div class="cert-layout">
      <!-- Deliberately not [data-reveal]: the certificate is the primary content
           of this page and must paint immediately (it is also the LCP element).
           Animating it in also put an opacity/transform transition on the same
           element that establishes the 3D rendering context for the tilt
           (perspective), which stalled mid-transition and left the frame blank. -->
      <div class="cert-frame-wrap">
        {visual}
        <div class="cert-actions no-print">{actions}</div>
      </div>

      <div>
        {verdict}

        <div class="cert-recipient">
          <span class="overline">Awarded to</span>
          <p class="cert-name">{e(c.name)}</p>
        </div>

        <div class="cert-id-row">
          <code>{e(c.id)}</code>
          <button class="copy-btn no-print" type="button" data-copy="{e(c.id)}" aria-label="Copy certificate ID">
            <svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-copy"/></svg>
          </button>
        </div>

        <dl class="meta-list" style="margin-top:var(--sp-5)">{meta_html}</dl>
      </div>
    </div>

    <div class="cert-sections">
      <section class="cert-section" data-reveal>
        <h2>{e(p.title)}</h2>
        <div class="prose">
          <p><strong style="color:var(--text-1)">{e(p.subtitle)}</strong></p>
          <p>{e(p.description)}</p>
        </div>
      </section>

{people_html}

      <section class="cert-section" data-reveal>
        <h2>About this verification</h2>
        <div class="assurance">
          <div class="assurance-item">
            <h3><svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-lock"/></svg> Permanent identifier</h3>
            <p>This identifier was assigned when the certificate was issued and is never reused,
               reassigned or released — even if the certificate is later suspended.</p>
          </div>
          <div class="assurance-item">
            <h3><svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-globe"/></svg> Authoritative record</h3>
            <p>This page is generated from the VNIAS certificate register. Where a certificate
               document differs from this record, this record prevails.</p>
          </div>
          <div class="assurance-item">
            <h3><svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-alert"/></svg> Report a discrepancy</h3>
            <p>If any detail here does not match the certificate you were shown, contact
               <a href="mailto:{CONTACT}">{CONTACT}</a> quoting the identifier above.</p>
          </div>
        </div>
      </section>

      <section class="cert-section no-print" data-reveal>
        <h2>More from this {e(cat['label_singular'].lower())}</h2>
        <div class="cluster">
          <a class="btn btn--ghost btn--sm" href="{base}{p.path}">All {len(p.certificates)} certificates</a>
          <a class="btn btn--ghost btn--sm" href="{base}verify/{cat['url_segment']}/">Browse {e(cat['label_plural'].lower())}</a>
          <a class="btn btn--ghost btn--sm" href="{base}verify/">Verify another ID</a>
        </div>
      </section>
    </div>
  </div>
</main>

<dialog class="lightbox" id="lightbox" aria-label="Certificate, enlarged">
  <button class="lightbox-close" type="button" aria-label="Close">
    <svg viewBox="0 0 24 24" width="20" height="20"><use href="#i-close"/></svg>
  </button>
  <img src="" alt="">
</dialog>
"""
        + footer(base, scripts=f'<script type="module" src="{base}assets/js/certificate.js"></script>\n')
    )


# ═══════════════════════════════════════════════════════════════════════════
# Manifests
# ═══════════════════════════════════════════════════════════════════════════

def write_manifests(projects: list[Project]) -> dict:
    by_cat: dict[str, list[Project]] = {c["key"]: [] for c in CATEGORIES}
    for p in projects:
        by_cat[p.category].append(p)
    for items in by_cat.values():
        items.sort(key=lambda p: p.event_date, reverse=True)

    stats = {"by_category": {}, "generated_at": date.today().isoformat()}
    total_certs = 0
    years: set[int] = set()

    for cat in CATEGORIES:
        items = by_cat[cat["key"]]
        count = sum(len(p.certificates) for p in items)
        total_certs += count
        years.update(int(p.issue_date[:4]) for p in items)

        write_json(DATA / "categories" / f"{cat['key']}.json", {
            "schema": 1,
            "category": cat["key"],
            "label": cat["label_plural"],
            "url_segment": cat["url_segment"],
            "certificate_count": count,
            "projects": [{
                "slug": p.slug, "title": p.title, "subtitle": p.subtitle,
                "event_date": p.event_date, "issue_date": p.issue_date,
                "certificate_count": len(p.certificates),
                "poster": f"/media/{cat['url_segment']}/{p.slug}/poster-800.webp",
                "mode": p.mode, "venue": p.venue or p.platform,
                "path": f"/{p.path}",
            } for p in items],
        })

        stats["by_category"][cat["key"]] = {
            "projects": len(items), "certificates": count,
            "label": cat["label_plural"],
        }

        for p in items:
            write_json(DATA / "projects" / cat["url_segment"] / f"{p.slug}.json", {
                "schema": 1, "shards": 1,
                "category": cat["key"], "slug": p.slug, "title": p.title,
                "subtitle": p.subtitle, "description": p.description,
                "event_date": p.event_date, "event_end_date": p.event_end_date,
                "issue_date": p.issue_date, "mode": p.mode,
                "venue": p.venue, "platform": p.platform,
                "people": [asdict(x) for x in p.people],
                "metadata": p.metadata,
                "media": {k: f"/media/{cat['url_segment']}/{p.slug}/{k}-1600.webp"
                          for k in ("poster", "cover", "banner")},
                # Name only — never an email address. See planning/03 §8.4.
                "certificates": [{"id": c.id, "name": c.name, "status": c.status}
                                 for c in p.certificates],
            })

    # Registry shards: <year>-<category>.json, keyed by ID.
    shards: dict[str, dict[str, str]] = {}
    for p in projects:
        seg = BY_KEY[p.category]["url_segment"]
        key = f"{p.issue_date[:4]}-{p.category}"
        for c in p.certificates:
            shards.setdefault(key, {})[c.id] = f"verify/{seg}/{p.slug}/{c.id}/"
    for key, table in shards.items():
        write_json(DATA / "registry" / f"{key}.json", table)

    write_json(DATA / "site.json", {
        "schema": 1,
        "organization": {"name": ORG, "short": "VNIAS", "url": SITE_URL, "email": CONTACT},
        "categories": [{k: c[k] for k in
                        ("key", "label_singular", "label_plural", "url_segment", "id_code", "icon", "hex")}
                       for c in CATEGORIES],
        "generated_at": date.today().isoformat(),
    })

    stats.update({
        "certificates_total": total_certs,
        "projects_total": len(projects),
        "categories_total": len(CATEGORIES),
        "years_covered": max(len(years), 1),
    })
    write_json(DATA / "stats.json", stats)
    return by_cat


def write_sitemap(projects: list[Project]) -> None:
    urls = [f"{SITE_URL}/", f"{SITE_URL}/verify/", f"{SITE_URL}/about/"]
    for c in CATEGORIES:
        urls.append(f"{SITE_URL}/verify/{c['url_segment']}/")
    for p in projects:
        urls.append(f"{SITE_URL}/{p.path}")
        urls.extend(f"{SITE_URL}/{p.path}{c.id}/"
                    for c in p.certificates if c.status != "suspended")

    body = "\n".join(f"  <url><loc>{u}</loc></url>" for u in urls)
    (ROOT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}\n</urlset>\n',
        encoding="utf-8")

    (ROOT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nDisallow: /data/\n\nSitemap: {SITE_URL}/sitemap.xml\n",
        encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# Sprite inlining — keeps pages buildless while avoiding four copies by hand
# ═══════════════════════════════════════════════════════════════════════════

MARKER = "<!--#include sprite-->"

# Matches an already-inlined sprite (with or without a leading comment fragment)
# so that re-running the build replaces it rather than stacking copies.
INLINED = re.compile(
    r'(?:external file, because Safari[\s\S]*?-->\s*)?'
    r'<svg width="0" height="0"[\s\S]*?</svg>\s*'
)


def inline_sprite() -> int:
    raw = (ASSETS / "brand" / "sprite.html").read_text(encoding="utf-8")
    sprite = re.sub(r"^\s*<!--[\s\S]*?-->\s*", "", raw).strip()

    count = 0
    for path in ROOT.rglob("*.html"):
        if path.name == "sprite.html":
            continue
        text = path.read_text(encoding="utf-8")
        if MARKER not in text:
            text, n = INLINED.subn(MARKER + "\n", text, count=1)
            if not n:
                continue
        path.write_text(text.replace(MARKER, sprite), encoding="utf-8")
        count += 1
    return count


# ═══════════════════════════════════════════════════════════════════════════
# Build
# ═══════════════════════════════════════════════════════════════════════════

def build(projects: list[Project]) -> None:
    by_cat = write_manifests(projects)

    for cat in CATEGORIES:
        items = by_cat[cat["key"]]
        write_html(VERIFY / cat["url_segment"] / "index.html",
                   render_category_page(cat, items))
        for p in items:
            write_html(VERIFY / cat["url_segment"] / p.slug / "index.html",
                       render_project_page(cat, p))
            for c in p.certificates:
                write_html(VERIFY / cat["url_segment"] / p.slug / c.id / "index.html",
                           render_certificate_page(cat, p, c))

    write_sitemap(projects)
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")

    pages = inline_sprite()
    certs = sum(len(p.certificates) for p in projects)
    print(f"  manifests   {len(list(DATA.rglob('*.json')))} json files")
    print(f"  pages       {pages} html files (sprite inlined)")
    print(f"  projects    {len(projects)}")
    print(f"  certificates{certs:>5}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the VNIAS certificate archive")
    ap.add_argument("--demo", action="store_true", help="seed and build a demo dataset")
    ap.add_argument("--clean", action="store_true", help="remove generated output first")
    args = ap.parse_args()

    if args.clean:
        for target in (DATA, VERIFY / "events", VERIFY / "sessions",
                       VERIFY / "workshops", VERIFY / "courses", CERTS, MEDIA):
            shutil.rmtree(target, ignore_errors=True)
        print("cleaned generated output")

    if args.demo:
        from demo_data import build_demo_dataset
        projects = build_demo_dataset(make_id, slugify)
        print(f"seeded demo dataset: {len(projects)} projects")
    else:
        projects = []

    build(projects)
    print("done")


if __name__ == "__main__":
    main()
