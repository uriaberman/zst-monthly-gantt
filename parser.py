# -*- coding: utf-8 -*-
"""
Parser: Adavot-style Gantt docx -> structured JSON.

Extracts: per-idea date / day / pillar / title / explanation / 2 visuals /
2 copy-on-visual / 2 captions. Default status = 'בעבודה'.
"""
import sys, io, json, re, argparse
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from docx import Document

IDEA_RE = re.compile(r'^רעיון\s+(\d+)\s*\|\s*(\d{1,2}\.\d{1,2}\.\d{2,4})\s*\(יום\s*(.+?)\)\s*\|\s*(.+?)$')
SEP_RE = re.compile(r'^—\s*—\s*—')

SECTIONS = {
    'explanation': re.compile(r'^הסבר לרעיון$'),
    'visuals': re.compile(r'^2 הצעות ויזואל$'),
    'copy_on_visual': re.compile(r'^2 הצעות קופי על ויזואל$'),
    'captions': re.compile(r'^2 הצעות קפשן$'),
}
SUB_A = re.compile(r"^(ויזואל|קופי|קפשן)\s*א'?\s*:?$")
SUB_B = re.compile(r"^(ויזואל|קופי|קפשן)\s*ב'?\s*:?$")


def parse_docx(path: Path):
    doc = Document(path)
    lines = [p.text for p in doc.paragraphs]
    items = []
    current = None
    section = None
    sub = None
    buf = []

    def flush_buf():
        nonlocal buf, current, section, sub
        if not current or section is None or sub is None:
            buf = []
            return
        text = '\n'.join(buf).strip()
        if not text:
            buf = []
            return
        if section == 'explanation':
            current['explanation'] = (current.get('explanation','') + '\n' + text).strip()
        else:
            current[section][sub] = text
        buf = []

    for raw in lines:
        line = raw.strip()
        if not line:
            buf.append('')
            continue

        m = IDEA_RE.match(line)
        if m:
            flush_buf()
            if current:
                items.append(current)
            current = {
                'num': int(m.group(1)),
                'date': m.group(2),
                'day': m.group(3).strip(),
                'pillar': m.group(4).strip(),
                'title': '',
                'explanation': '',
                'visuals': {'a': '', 'b': ''},
                'copy_on_visual': {'a': '', 'b': ''},
                'captions': {'a': '', 'b': ''},
                'status': 'בעבודה',
            }
            section = 'title'
            sub = None
            continue

        if SEP_RE.match(line):
            flush_buf()
            section = None
            sub = None
            continue

        if current is None:
            continue

        # title line is the first non-empty after header
        if section == 'title':
            current['title'] = line
            section = None
            sub = None
            continue

        matched = False
        for key, rgx in SECTIONS.items():
            if rgx.match(line):
                flush_buf()
                section = key
                sub = 'a' if key == 'explanation' else None
                matched = True
                break
        if matched:
            continue

        if SUB_A.match(line):
            flush_buf()
            sub = 'a'
            continue
        if SUB_B.match(line):
            flush_buf()
            sub = 'b'
            continue

        buf.append(line)

    flush_buf()
    if current:
        items.append(current)

    return items


def normalize_date(s: str) -> str:
    """Convert 'DD.M.YY' or 'DD.MM.YY' to ISO 'YYYY-MM-DD' (assume 20YY)."""
    parts = s.split('.')
    d, m, y = parts
    y = int(y)
    if y < 100:
        y += 2000
    return f'{y:04d}-{int(m):02d}-{int(d):02d}'


PILLAR_CANONICAL = {
    'מאחורי המספרים': 'numbers',
    'השאלה השבועית': 'question',
    'השאלה ששמעתי': 'question',
    'רייל': 'reel',
    'רילס': 'reel',
    'קולות מהשטח': 'voices',
    'עוגן שבועות': 'anchor',
    'אדווקסי': 'advocacy',
    'גשר חודשים': 'anchor',
    'אנחנו כאן': 'community',
    'חמישי בנחלים': 'community',
    'ראש חודש': 'anchor',
    'יום אבא': 'anchor',
    'ידעתם ש': 'advocacy',
}

PILLAR_LABEL = {
    'numbers': 'מאחורי המספרים',
    'question': 'השאלה השבועית',
    'reel': 'רילס',
    'voices': 'קולות מהשטח',
    'anchor': 'עוגן',
    'advocacy': 'אדווקסי',
    'community': 'אנחנו כאן',
}


def classify_pillar(raw: str) -> str:
    for key, val in PILLAR_CANONICAL.items():
        if key in raw:
            return val
    return 'other'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('docx')
    ap.add_argument('--out', required=True)
    ap.add_argument('--client', required=True, help='Client name (Hebrew)')
    ap.add_argument('--period', required=True, help='e.g. "20.5-30.6.2026"')
    args = ap.parse_args()

    items = parse_docx(Path(args.docx))
    for it in items:
        it['date_iso'] = normalize_date(it['date'])
        it['pillar_key'] = classify_pillar(it['pillar'])
        it['pillar_short'] = PILLAR_LABEL.get(it['pillar_key'], it['pillar'])

    out = {
        'client': args.client,
        'period': args.period,
        'count': len(items),
        'items': items,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'WROTE {args.out}: {len(items)} items')
    for it in items[:5]:
        print(f"  #{it['num']:>2} {it['date_iso']} ({it['day']}) [{it['pillar_key']}] {it['title'][:50]}")


if __name__ == '__main__':
    main()
