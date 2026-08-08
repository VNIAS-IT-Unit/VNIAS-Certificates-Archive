# Working on this repository

## What lives here

Two halves, kept deliberately separate:

| Half | Paths | Who writes it |
|------|-------|---------------|
| **The shell** | `index.html`, `verify/index.html`, `about/`, `404.html`, `assets/**`, `tools/**` | People. Changes rarely. |
| **The archive** | `verify/<category>/**`, `certificates/**`, `media/**`, `data/**` | The VNIAS Certificate Management System, on publish. |

Editing the archive by hand will be overwritten on the next publish, and worse,
will disagree with the desktop application's database — which is the source of
truth for what was actually issued.

## Never commit demo data

`tools/build_site.py --demo` generates a realistic corpus (invented participants,
fabricated certificates, working QR codes) for reviewing the design locally.

**It must never be pushed here.** This repository is the official verification
portal: a fabricated record published to it is indistinguishable from a genuine
one to anyone who visits, which destroys the only thing the site is for.

Before committing, make sure the archive is clean:

```bash
python tools/build_site.py --clean
```

## Local preview

```bash
uv run --with pillow --with segno python tools/build_site.py --demo --clean
```

```bash
python -m http.server 8899
```

Then open <http://127.0.0.1:8899/>. Run `--clean` again before you commit.

## Design and data contracts

The design system, information architecture, JSON schemas and repository layout
are specified in the desktop application's planning documents — see
`DesktopSystem/planning/07-static-website.md`. The shell's CSS class names and
the JSON shapes are a contract the desktop application depends on; changing
either without changing the generator will break publishing.

## Privacy

Published files carry only what is printed on the face of a certificate: the
recipient's name, the programme and the dates. **No email addresses, ever.** The
generator enforces this with a whitelist and a pre-publish scan; do not add
fields to the published payload without reading
`DesktopSystem/planning/03-data-state-security.md` §8.4 first.
