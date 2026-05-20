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


# Content type classification - 3 buckets only by FORMAT (post vs story vs reel).
# The original pillar name stays as the human-readable label inside each cell;
# the type drives color only (less visual noise across the calendar).
# 4 content types only - drive color
TYPE_CANONICAL = {
    # video / motion → reel
    'רייל': 'reel',
    'רילס': 'reel',
    'סרטון': 'reel',
    'reel': 'reel',
    # carousel (multi-slide post)
    'קרוסלה': 'carousel',
    'carousel': 'carousel',
    # ephemeral story
    'סטורי': 'story',
    'סטוריז': 'story',
    'story': 'story',
    'stories': 'story',
}

TYPE_LABEL = {
    'post': 'פוסט',
    'carousel': 'קרוסלה',
    'story': 'סטורי',
    'reel': 'רילס',
}


def classify_type(raw: str) -> str:
    """Default = post (single-image / text post). Use type tokens in pillar name."""
    low = raw.lower()
    for key, val in TYPE_CANONICAL.items():
        if key in low or key in raw:
            return val
    return 'post'


# Patterns that indicate a "meta" intro sentence (skip if leading)
META_INTRO_PREFIXES = (
    'פתיחת הסדרה', 'סגירת הסדרה', 'פינה חדשה', 'הרייל הראשון',
    'הרייל ה', 'הפוסט הראשון', 'פוסט אדווקסי', 'פתיחת ה',
)

def extract_short_and_source(full_explanation: str) -> tuple[str, str]:
    """Return (short_explanation, source) from the long docx explanation.
    Strategy:
      - Source = last line starting with 'מקור:' (cleaned)
      - Short = first 1-2 sentences from the FIRST paragraph (skipping meta intros)
    """
    if not full_explanation:
        return '', ''

    text = full_explanation.strip()

    # Extract source line(s)
    source = ''
    src_lines = []
    cleaned_lines = []
    for line in text.split('\n'):
        ls = line.strip()
        if ls.startswith('מקור:') or ls.startswith('מקורות:'):
            src_lines.append(ls.split(':', 1)[1].strip() if ':' in ls else ls)
        else:
            cleaned_lines.append(line)
    if src_lines:
        source = ' | '.join(src_lines)

    body = '\n'.join(cleaned_lines).strip()
    if not body:
        return '', source

    # Take the first paragraph (until the first blank line)
    first_para = body.split('\n\n')[0].strip()

    # Split into sentences (on period followed by space/newline, or by exclamation/question marks)
    import re
    sentences = re.split(r'(?<=[.!?])\s+', first_para)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return '', source

    # Skip leading meta intros
    skip = 0
    while skip < len(sentences) and any(sentences[skip].startswith(p) for p in META_INTRO_PREFIXES):
        skip += 1

    if skip >= len(sentences):
        skip = 0  # fall back to first sentence if all skipped

    # Take 1-2 sentences (up to ~180 chars)
    short = sentences[skip]
    if skip + 1 < len(sentences) and len(short) < 100:
        short = (short + ' ' + sentences[skip + 1]).strip()

    if len(short) > 200:
        short = short[:197].rstrip() + '...'

    return short, source


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
        it['type_key'] = classify_type(it['pillar'])
        it['type_label'] = TYPE_LABEL[it['type_key']]
        it['pillar_label'] = it['pillar'].rsplit('#', 1)[0].strip().rstrip('-').strip() or it['pillar']
        # Short explanation (1-2 sentences) + source extracted from long explanation
        short, source = extract_short_and_source(it.get('explanation', ''))
        it['short_explanation'] = short
        it['source'] = source

    out = {
        'client': args.client,
        'period': args.period,
        'count': len(items),
        'items': items,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'WROTE {args.out}: {len(items)} items')
    for it in items[:5]:
        print(f"  #{it['num']:>2} {it['date_iso']} ({it['day']}) [{it['type_key']}] {it['title'][:50]}")


if __name__ == '__main__':
    main()
