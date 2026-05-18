# ZST Monthly Gantt

Branded HTML monthly content calendar viewer for Seliger Shomron clients.

**Pilot live:** https://uriaberman.github.io/zst-monthly-gantt/adavot/

## Pipeline

```
client docx/text → parser.py → data.json → build.py → docs/<client>/index.html → GitHub Pages
```

## Build

```bash
python parser.py "<path-to-gantt.docx>" --out pilots/<client>/data.json \
  --client "<שם לקוח>" --period "<DD.M - DD.M.YYYY>"

python build.py --data pilots/<client>/data.json --logo assets/logo.png \
  --out docs/<client>/index.html
```

## Features

- RTL Hebrew layout, landscape (May + June side-by-side)
- Hebrew date (gematria) per cell + Gregorian
- Holidays auto-marked (Shavuot, Rosh Chodesh, יום אבא, …)
- 7 content pillar colors (numbers / question / reel / voices / anchor / advocacy / community)
- 4 statuses (בעבודה · בעיצוב · ממתין לאישור · אושר)
- Friday/Saturday differentiated by warm cream background
- Click-to-expand modal: full explanation + 2 visuals + 2 copy + 2 captions
