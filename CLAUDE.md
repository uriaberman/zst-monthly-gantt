# CLAUDE.md — zst-monthly-gantt

## What this is
Pipeline to produce branded HTML monthly content Gantts for Seliger Shomron clients.
Source = Hebrew docx/text with idea cards (per Adavot template). Output = static HTML
deployed to GitHub Pages, shareable URL per client/month.

## Stack
- Python 3.13 (parser + builder, no framework)
- `python-docx` — reads source Gantt docx
- `pyluach` — Hebrew date conversion (gematria)
- Static HTML/CSS/JS — no build tool, no runtime dependency

## Pipeline
```
client docx/text  →  parser.py  →  data.json  →  build.py  →  docs/<client>/index.html
                                                                    ↓
                                                          GitHub Pages (auto-deploy)
```

## Commands
```bash
python parser.py "<path-to-gantt.docx>" \
  --out pilots/<client>/data.json \
  --client "<שם לקוח>" --period "<DD.M - DD.M.YYYY>"

python build.py \
  --data pilots/<client>/data.json \
  --logo assets/logo.png \
  --out docs/<client>/index.html

git add -A && git commit -m "update <client> gantt" && git push
```

## Structure
- `parser.py` — extracts ideas from docx into structured JSON.
  Recognizes Adavot template: `רעיון N | DD.M.YY (יום X) | פינה` → title → הסבר/ויזואל/קופי/קפשן blocks.
- `build.py` — renders JSON to HTML. Side-by-side landscape calendars, RTL, Hebrew dates,
  holiday markers, 7 pillar colors, 4 status colors, click-to-expand modal.
- `assets/logo.png` — Seliger Shomron logo (embedded base64 into output).
- `pilots/<client>/` — working dir per client (data.json + intermediate index.html).
- `docs/` — published to GitHub Pages root.
  - `docs/index.html` — clients listing page.
  - `docs/<client>/index.html` — per-client gantt.

## Pillar classification
Parser maps Hebrew pillar names to canonical keys (`numbers`, `question`, `reel`,
`voices`, `anchor`, `advocacy`, `community`). Add new mappings in `parser.py::PILLAR_CANONICAL`.

## Statuses
4 fixed: `בעבודה` (gray), `בעיצוב` (blue), `ממתין לאישור` (orange), `אושר` (green).
Default = `בעבודה`. Set in source docx via convention TBD, or hand-edit JSON before build.

## Holidays
Currently hard-coded for May-June 2026 in `build.py::HOLIDAYS_2026`. Expand or move to
`pyluach.hebrewcal.Year(...).get_holidays()` when generalizing past pilot.

## Deploy
GitHub Pages enabled on `main` branch, source `/docs`. URL:
`https://uriaberman.github.io/zst-monthly-gantt/<client>/`

## Gotchas
- docx file must be `.docx` (binary, opened via python-docx). `.gdoc` won't work.
- Hebrew encoding: scripts must run with `python -X utf8` on Windows or set
  `sys.stdout = io.TextIOWrapper(...)` for clean console output.
- Logo embedded as base64 → output HTML self-contained, no external assets needed.
- Outside-month cells (previous/next month edge days) must NOT render items in DOM
  even though hidden by CSS — otherwise items appear duplicated across month grids.

## Next iterations (not built yet)
- Status column in source docx → parser reads instead of default
- Smart placement of dateless items (suggest dates from content semantics)
- Generic Hebrew holiday lookup (replace hardcoded HOLIDAYS_2026)
- Auto-pull visuals from a `visuals/` folder by filename date prefix
- Package as a Claude skill (`zst-monthly-gantt` skill in `~/.claude/skills/`)
