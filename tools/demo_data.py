"""
Demo dataset for the VNIAS certificate archive.

Produces a realistic, reviewable corpus so the website can be validated before
the desktop application exists: eight programmes across the four categories,
international participant names (including deliberately long ones, to exercise
typography), real scannable QR codes, and rendered certificate artwork.

Nothing here ships to production — it exists so that layout, contrast, empty
states, long-name wrapping and the suspended state can all be seen and judged.

Requires: pillow, segno
"""

from __future__ import annotations

import io
import random
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import segno

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "assets" / "brand"
CERTS = ROOT / "certificates"
MEDIA = ROOT / "media"

SITE_URL = "https://vnias.org"

# Deterministic output: rebuilding the demo must not churn the git history.
RNG = random.Random(20260803)

CERT_W, CERT_H = 2000, 1414
WEB_W = 1600

INK = (14, 26, 33)
TEAL = (10, 110, 143)
TEAL_D = (5, 61, 80)
LIME = (138, 170, 10)
PAPER = (248, 246, 240)
MUTED = (110, 128, 138)


# ── Fonts ────────────────────────────────────────────────────────────────

def _font(names: list[str], size: int) -> ImageFont.FreeTypeFont:
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def serif(size, bold=False, italic=False):
    stem = "georgia"
    if bold and italic:
        stem += "z"
    elif bold:
        stem += "b"
    elif italic:
        stem += "i"
    return _font([f"{stem}.ttf", "times.ttf", "DejaVuSerif.ttf"], size)


def sans(size, bold=False):
    return _font(["segoeuib.ttf" if bold else "segoeui.ttf",
                  "arialbd.ttf" if bold else "arial.ttf",
                  "DejaVuSans.ttf"], size)


def mono(size):
    return _font(["consola.ttf", "cour.ttf", "DejaVuSansMono.ttf"], size)


# ── Drawing helpers ──────────────────────────────────────────────────────

def centred(draw, y, text, font, fill, width=CERT_W, tracking=0):
    if tracking:
        total = sum(draw.textlength(ch, font=font) + tracking for ch in text) - tracking
        x = (width - total) / 2
        for ch in text:
            draw.text((x, y), ch, font=font, fill=fill)
            x += draw.textlength(ch, font=font) + tracking
        return
    w = draw.textlength(text, font=font)
    draw.text(((width - w) / 2, y), text, font=font, fill=fill)


def fit_centred(draw, y, text, fill, max_w, start=104, min_size=52, italic=True):
    """Shrink-to-fit — the same policy the desktop renderer will apply."""
    size = start
    while size > min_size:
        f = serif(size, italic=italic)
        if draw.textlength(text, font=f) <= max_w:
            break
        size -= 2
    f = serif(size, italic=italic)
    centred(draw, y, text, f, fill)
    return f


def gradient(size, c1, c2, angle_horizontal=True):
    w, h = size
    base = Image.new("RGB", (w, h), c1)
    top = Image.new("RGB", (w, h), c2)
    n = w if angle_horizontal else h
    mask = Image.new("L", (w, h))
    md = ImageDraw.Draw(mask)
    for i in range(n):
        v = int(255 * (i / max(n - 1, 1)))
        if angle_horizontal:
            md.line([(i, 0), (i, h)], fill=v)
        else:
            md.line([(0, i), (w, i)], fill=v)
    base.paste(top, (0, 0), mask)
    return base


# ── Certificate artwork ──────────────────────────────────────────────────

_mark_cache: Image.Image | None = None


def mark() -> Image.Image:
    global _mark_cache
    if _mark_cache is None:
        _mark_cache = Image.open(BRAND / "vnias-mark.png").convert("RGBA")
    return _mark_cache


def render_certificate(out: Path, *, name: str, cert_id: str, project, category_label: str,
                       verify_url: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (CERT_W, CERT_H), PAPER)
    d = ImageDraw.Draw(img)

    # Corner wash in the brand hues, kept subtle so text stays legible.
    wash = Image.new("RGB", (CERT_W, CERT_H), PAPER)
    wd = ImageDraw.Draw(wash)
    wd.ellipse([-520, -620, 780, 520], fill=(226, 238, 243))
    wd.ellipse([CERT_W - 660, CERT_H - 520, CERT_W + 420, CERT_H + 380], fill=(238, 243, 220))
    img = Image.blend(img, wash, 0.85)
    d = ImageDraw.Draw(img)

    # Frame: heavy teal rule outside, hairline inside, lime accent at the corners.
    d.rectangle([34, 34, CERT_W - 34, CERT_H - 34], outline=TEAL_D, width=6)
    d.rectangle([52, 52, CERT_W - 52, CERT_H - 52], outline=(196, 208, 214), width=2)
    for x0, y0, x1, y1 in (
        (34, 34, 190, 40), (34, 34, 40, 190),
        (CERT_W - 190, CERT_H - 40, CERT_W - 34, CERT_H - 34),
        (CERT_W - 40, CERT_H - 190, CERT_W - 34, CERT_H - 34),
    ):
        d.rectangle([x0, y0, x1, y1], fill=LIME)

    # Emblem
    m = mark().copy()
    m.thumbnail((190, 190), Image.LANCZOS)
    img.paste(m, ((CERT_W - m.width) // 2, 108), m)

    centred(d, 320, "VITANOVA INTERNATIONAL ALLIANCE FOR SCIENCES",
            sans(27, bold=True), TEAL_D, tracking=5)

    centred(d, 396, f"Certificate of {'Completion' if project.category == 'course' else 'Participation'}",
            serif(66, bold=True), INK)

    d.line([(CERT_W / 2 - 150, 492), (CERT_W / 2 + 150, 492)], fill=LIME, width=3)

    centred(d, 556, "This is to certify that", sans(30), MUTED)
    fit_centred(d, 626, name, TEAL_D, max_w=CERT_W - 460)

    centred(d, 790, f"has successfully participated in the {category_label.lower()}", sans(30), MUTED)

    title = project.title
    size = 50
    while size > 30 and d.textlength(title, font=serif(size, bold=True)) > CERT_W - 460:
        size -= 2
    centred(d, 848, title, serif(size, bold=True), INK)

    where = project.venue if project.mode != "online" else project.platform
    centred(d, 930, f"{_pretty_date(project.event_date)}  ·  {where}", sans(27), MUTED)

    # Signature blocks
    for cx, label, who in ((560, "Director, VNIAS", "Ghulam Murtaza"),
                           (CERT_W - 560, "Programme Lead", project.people[0].name if project.people else "VNIAS")):
        d.line([(cx - 210, 1168), (cx + 210, 1168)], fill=(150, 165, 172), width=2)
        w = d.textlength(who, font=serif(32, italic=True))
        d.text((cx - w / 2, 1112), who, font=serif(32, italic=True), fill=INK)
        w = d.textlength(label, font=sans(23))
        d.text((cx - w / 2, 1184), label, font=sans(23), fill=MUTED)

    # QR — a real, scannable code pointing at the verification page. Rendered in
    # memory and resampled with NEAREST so module edges stay hard; any smooth
    # resampling of a QR softens the modules and costs scan reliability.
    buf = io.BytesIO()
    segno.make(verify_url, error="m").save(
        buf, kind="png", scale=8, border=2, dark="#053d50", light="#f8f6f0")
    buf.seek(0)
    qr_img = Image.open(buf).convert("RGB").resize((236, 236), Image.NEAREST)
    img.paste(qr_img, (CERT_W - 236 - 96, CERT_H - 236 - 96))

    d.text((96, CERT_H - 196), "CERTIFICATE ID", font=sans(21, bold=True), fill=MUTED)
    d.text((96, CERT_H - 162), cert_id, font=mono(30), fill=TEAL_D)
    d.text((96, CERT_H - 118), "Verify at", font=sans(19), fill=MUTED)
    d.text((96, CERT_H - 92), verify_url.replace("https://", ""), font=sans(19), fill=TEAL)

    out.parent.mkdir(parents=True, exist_ok=True)
    web = img.resize((WEB_W, round(CERT_H * WEB_W / CERT_W)), Image.LANCZOS)
    web.save(out, "WEBP", quality=82, method=4)


def _pretty_date(iso: str) -> str:
    y, m, dd = (int(p) for p in iso.split("-"))
    months = ("January February March April May June July August September "
              "October November December").split()
    return f"{dd} {months[m - 1]} {y}"


# ── Project media (poster / cover / banner) ──────────────────────────────

def render_media(project, url_segment: str, hex_accent: str) -> None:
    out_dir = MEDIA / url_segment / project.slug
    out_dir.mkdir(parents=True, exist_ok=True)
    accent = tuple(int(hex_accent[i:i + 2], 16) for i in (1, 3, 5))

    for kind, (w, h) in (("poster", (1600, 900)), ("cover", (1600, 900)), ("banner", (1600, 600))):
        base = gradient((w, h), (6, 14, 20), (max(accent[0] - 120, 4),
                                              max(accent[1] - 110, 12),
                                              max(accent[2] - 90, 20)))
        d = ImageDraw.Draw(base, "RGBA")

        # Concentric arcs echoing the logo's swoosh.
        for i in range(7):
            r = int(w * (0.34 + i * 0.13))
            cx, cy = int(w * 0.78), int(h * 1.16)
            d.arc([cx - r, cy - r, cx + r, cy + r], 180, 360,
                  fill=(*accent, 46 - i * 5), width=3)

        for i in range(26):
            x = RNG.randint(0, w)
            y = RNG.randint(0, h)
            rr = RNG.randint(1, 3)
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(*accent, RNG.randint(40, 130)))

        # No title text is drawn into the artwork. The project hero and the card
        # body both render the title as live HTML, so baking it into the image
        # produced a visible duplicate behind the real heading.

        for width_px in (1600, 800, 400):
            scaled = base.resize((width_px, round(h * width_px / w)), Image.LANCZOS)
            scaled.save(out_dir / f"{kind}-{width_px}.webp", "WEBP", quality=80, method=4)


# ── Participants ─────────────────────────────────────────────────────────

FIRST = ["Fatima", "Ahmed", "Ayesha", "Muhammad", "Zainab", "Hassan", "Mariam", "Bilal",
         "Sara", "Usman", "Amina", "Omar", "Noor", "Ibrahim", "Hira", "Yusuf",
         "Wei", "Mei", "Kenji", "Yuki", "Anjali", "Rohan", "Priya", "Arjun",
         "Elena", "Marco", "Sofia", "Lukas", "Chiamaka", "Kwame", "Amara", "Thabo",
         "Layla", "Karim", "Rania", "Tariq", "Nadia", "Farhan", "Zoya", "Danish"]
LAST = ["Rehman", "Khan", "Siddiqui", "Malik", "Qureshi", "Ansari", "Farooqi", "Baig",
        "Chaudhry", "Sheikh", "Zhang", "Chen", "Tanaka", "Nakamura", "Sharma", "Patel",
        "Iyer", "Rossi", "Novak", "Fernandez", "Okonkwo", "Mensah", "Adeyemi", "Dlamini",
        "Haddad", "Aziz", "Nasser", "Bhatti", "Jamil", "Raza"]
LONG_NAMES = [
    "María José van der Berg-Rodríguez",
    "Muhammad Abdur Rahman Al-Sheikh Qureshi",
    "Chidinma Oluwaseun Adebayo-Nwachukwu",
]


def participants(n: int, rng: random.Random) -> list[str]:
    names, seen = [], set()
    # Seed a few deliberately long names so shrink-to-fit is visible in review.
    for long_name in LONG_NAMES[: max(1, n // 12)]:
        names.append(long_name)
        seen.add(long_name)
    while len(names) < n:
        candidate = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        if rng.random() < 0.22:
            candidate = f"{rng.choice(FIRST)} {rng.choice(FIRST)} {rng.choice(LAST)}"
        if candidate in seen:
            continue
        seen.add(candidate)
        names.append(candidate)
    rng.shuffle(names)
    return names


# ── The dataset ──────────────────────────────────────────────────────────

SPEC = [
    ("event", "AI in Life Sciences Summit 2026",
     "Two days on machine learning in genomics, drug discovery and clinical research",
     "The inaugural VNIAS summit brought together researchers, clinicians and engineers to examine "
     "how machine learning is reshaping the life sciences. Sessions covered foundation models for "
     "protein structure, federated learning across hospital networks, and the regulatory landscape "
     "for algorithmic diagnostics.",
     "2026-03-12", "2026-03-13", "2026-03-16", "hybrid", "Karachi Expo Centre, Pakistan", "Zoom", 26,
     [("Dr. Sadia Rehman", "speaker", "Professor of Computational Biology", "Aga Khan University"),
      ("Prof. Marco Bellini", "speaker", "Chair of Bioinformatics", "University of Bologna"),
      ("Ghulam Murtaza", "organizer", "Founder & Director", "VNIAS"),
      ("Dr. Amina Yusuf", "organizer", "Programme Director", "VNIAS")]),

    ("event", "International Research Collaboration Conference",
     "Building cross-border research partnerships in the global south",
     "A one-day conference on the practicalities of international research collaboration: funding "
     "instruments, data-sharing agreements, authorship conventions and the institutional support "
     "structures that make multi-country studies viable.",
     "2026-05-21", "2026-05-21", "2026-05-24", "online", "", "Microsoft Teams", 19,
     [("Dr. Elena Novak", "speaker", "Director of Research Development", "Charles University"),
      ("Kwame Mensah", "speaker", "Senior Research Fellow", "University of Ghana"),
      ("Ghulam Murtaza", "organizer", "Founder & Director", "VNIAS")]),

    ("session", "Genomic Data Ethics — A Practitioner's Webinar",
     "Consent, re-identification risk and equitable benefit sharing",
     "An evening session examining the ethical questions that arise once genomic data leaves the "
     "laboratory: what informed consent means for data that can be re-analysed indefinitely, how "
     "re-identification risk is actually assessed, and who benefits from population-scale studies.",
     "2026-02-18", "2026-02-18", "2026-02-19", "online", "", "Zoom", 14,
     [("Dr. Layla Haddad", "speaker", "Bioethicist", "American University of Beirut"),
      ("Dr. Amina Yusuf", "host", "Programme Director", "VNIAS")]),

    ("session", "Careers in Computational Biology",
     "A guided session for students entering the field",
     "A practical career session for final-year students and early graduates: which skills employers "
     "actually screen for, how to build a portfolio without a formal research post, and the routes "
     "into industry, academia and public health informatics.",
     "2026-04-09", "2026-04-09", "2026-04-10", "online", "", "Google Meet", 22,
     [("Rohan Iyer", "speaker", "Senior Bioinformatician", "Genomics England"),
      ("Dr. Sadia Rehman", "speaker", "Professor of Computational Biology", "Aga Khan University")]),

    ("workshop", "Python for Bioinformatics Bootcamp",
     "Five days of hands-on scientific computing, from first script to reproducible pipeline",
     "An intensive bootcamp taking participants from basic Python syntax to a working, reproducible "
     "analysis pipeline. Sessions covered sequence handling with Biopython, dataframe manipulation, "
     "plotting for publication, environment management, and version control for research code.",
     "2026-06-08", "2026-06-12", "2026-06-15", "in_person", "VNIAS Training Lab, Islamabad", "", 31,
     [("Danish Jamil", "speaker", "Lead Instructor", "VNIAS"),
      ("Priya Sharma", "speaker", "Research Software Engineer", "EMBL-EBI"),
      ("Dr. Amina Yusuf", "organizer", "Programme Director", "VNIAS")]),

    ("workshop", "CRISPR Laboratory Techniques",
     "Guide design, delivery and validation, at the bench",
     "A laboratory workshop covering the full CRISPR-Cas9 workflow: guide RNA design and off-target "
     "assessment, delivery into mammalian cell lines, selection strategies, and validation by "
     "sequencing. Every participant completed an independent edit and validated the result.",
     "2026-07-14", "2026-07-16", "2026-07-20", "in_person", "Molecular Biology Suite, Lahore", "", 16,
     [("Dr. Hassan Baig", "speaker", "Principal Investigator", "University of the Punjab"),
      ("Zainab Ansari", "organizer", "Laboratory Coordinator", "VNIAS")]),

    ("course", "Certificate Course in Molecular Biology",
     "An eight-week structured programme with assessment",
     "An eight-week course covering the central dogma in depth, gene regulation, recombinant DNA "
     "technology and modern sequencing platforms. Assessment comprised weekly problem sets, a "
     "practical report and a final written examination.",
     "2026-01-13", "2026-03-06", "2026-03-10", "hybrid", "VNIAS Academic Centre, Islamabad", "Moodle", 24,
     [("Prof. Tariq Nasser", "speaker", "Course Convenor", "Quaid-i-Azam University"),
      ("Dr. Sadia Rehman", "speaker", "Module Lead", "Aga Khan University"),
      ("Ghulam Murtaza", "organizer", "Founder & Director", "VNIAS")]),

    ("course", "Scientific Writing and Publishing",
     "Six weeks on writing, submitting and defending a research paper",
     "A six-week course on the craft of scientific communication: structuring a paper around its "
     "claim, writing methods that can actually be reproduced, choosing a journal honestly, handling "
     "peer review, and the ethics of authorship and citation.",
     "2026-04-06", "2026-05-15", "2026-05-19", "online", "", "Moodle", 18,
     [("Dr. Elena Novak", "speaker", "Course Convenor", "Charles University"),
      ("Dr. Amina Yusuf", "organizer", "Programme Director", "VNIAS")]),
]


def build_demo_dataset(make_id, slugify):
    """Returns a list of build_site.Project, with all artwork rendered."""
    from build_site import Project, Person, BY_KEY, Certificate

    projects = []
    for (cat, title, subtitle, description, start, end, issued, mode, venue,
         platform, count, people_spec) in SPEC:
        meta = BY_KEY[cat]
        slug = slugify(title)

        p = Project(
            category=cat, slug=slug, title=title, subtitle=subtitle,
            description=description, event_date=start, event_end_date=end,
            issue_date=issued, mode=mode, venue=venue, platform=platform,
            people=[Person(name=n, role=r, title=t, affiliation=a) for n, r, t, a in people_spec],
            metadata={"accreditation": "VNIAS Internal", "language": "English"},
        )
        year = int(issued[:4])
        for name in participants(count, RNG):
            p.certificates.append(Certificate(id=make_id(meta["id_code"], year, RNG), name=name))

        projects.append(p)

    # One suspended certificate, so the suspended state is reviewable.
    target = projects[4].certificates[3]
    target.status = "suspended"
    target.suspended_on = "2026-06-28"

    print("  rendering media and certificates…")
    for p in projects:
        meta = BY_KEY[p.category]
        render_media(p, meta["url_segment"], meta["hex"])
        for c in p.certificates:
            if c.status == "suspended":
                continue  # a suspended certificate's image is never published
            render_certificate(
                CERTS / meta["url_segment"] / p.slug / f"{c.id}.webp",
                name=c.name, cert_id=c.id, project=p,
                category_label=meta["label_singular"],
                verify_url=f"{SITE_URL}/verify/{meta['url_segment']}/{p.slug}/{c.id}/",
            )
        print(f"    {p.slug}: {len(p.certificates)} certificates")

    return projects
