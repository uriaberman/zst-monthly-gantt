# -*- coding: utf-8 -*-
"""
Generic Gantt parser: docx / pdf / txt / md → structured JSON.

Auto-detects document structure:
  - 'adavot'         : 'רעיון N | DD.M.YY (יום X) | pillar' with sub-sections
  - 'shlichut_horaa' : '< תוכן N' blocks with FIELD: value rows
  - 'numbered'       : '1. ...' or '1) ...' simple numbered list
  - 'unknown'        : returns items with null dates for Smart Placement

Items missing dates have date=None / day=None → consumer must run smart_placement
before passing to build.py.
"""
import sys, io, json, re, argparse
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


# ============================================================================
# TEXT EXTRACTION
# ============================================================================

def extract_lines(path: Path) -> list[str]:
    """Read any supported file format → list of text lines."""
    ext = path.suffix.lower()
    if ext == '.docx':
        from docx import Document
        return [p.text for p in Document(path).paragraphs]
    if ext == '.pdf':
        import pdfplumber
        out_lines = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ''
                out_lines.extend(t.split('\n'))
        return out_lines
    if ext in ('.txt', '.md'):
        return path.read_text(encoding='utf-8').splitlines()
    raise ValueError(f"Unsupported format: {ext}. Use .docx / .pdf / .txt / .md")


# ============================================================================
# FORMAT DETECTION
# ============================================================================

RX_ADAVOT = re.compile(r'^רעיון\s+\d+\s*\|\s*\d{1,2}\.\d{1,2}\.\d{2,4}\s*\(יום\s*[^)]+\)\s*\|', re.MULTILINE)
RX_SHLICHUT = re.compile(r'^<\s*תוכן\s+\d+', re.MULTILINE)
RX_NUMBERED = re.compile(r'^\d+[.)]\s+\S', re.MULTILINE)


def detect_format(lines: list[str]) -> str:
    sample = '\n'.join(lines[:300])
    if RX_ADAVOT.search(sample):
        return 'adavot'
    if RX_SHLICHUT.search(sample):
        return 'shlichut_horaa'
    if RX_NUMBERED.search(sample):
        return 'numbered'
    return 'unknown'


# ============================================================================
# ADAVOT FORMAT (original, dates + pillars + sub-sections)
# ============================================================================

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


def parse_adavot(lines: list[str]) -> list[dict]:
    items, current, section, sub, buf = [], None, None, None, []

    def flush():
        nonlocal buf
        if not current or section is None or sub is None:
            buf = []; return
        text = '\n'.join(buf).strip()
        if not text:
            buf = []; return
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
            flush()
            if current: items.append(current)
            current = _empty_item(int(m.group(1)))
            current['date'] = m.group(2)
            current['day'] = m.group(3).strip()
            current['pillar'] = m.group(4).strip()
            section, sub = 'title', None
            continue
        if SEP_RE.match(line):
            flush(); section, sub = None, None; continue
        if current is None: continue
        if section == 'title':
            current['title'] = line
            section, sub = None, None; continue
        matched = False
        for key, rgx in SECTIONS.items():
            if rgx.match(line):
                flush(); section = key; sub = 'a' if key == 'explanation' else None
                matched = True; break
        if matched: continue
        if SUB_A.match(line): flush(); sub = 'a'; continue
        if SUB_B.match(line): flush(); sub = 'b'; continue
        buf.append(line)

    flush()
    if current: items.append(current)
    return items


# ============================================================================
# SHLICHUT HORAA FORMAT (`< תוכן N` blocks, no dates in source)
# ============================================================================

SHL_BLOCK_RE = re.compile(r'^<\s*תוכן\s+(\d+)\b')
SHL_FIELD_RE = re.compile(r"^(רעיון|ויז'ואל|ויזואל|קופי ויז'ואל|קופי ויזואל|קופי נלווה|הסבר|מקור)\s*:\s*(.*)$")


def parse_shlichut_horaa(lines: list[str]) -> list[dict]:
    items, current = [], None
    last_field = None

    for raw in lines:
        line = raw.strip()
        if not line:
            last_field = None
            continue

        m = SHL_BLOCK_RE.match(line)
        if m:
            if current: items.append(current)
            current = _empty_item(int(m.group(1)))
            # No date / day - will be set by Smart Placement
            last_field = None
            continue

        if current is None:
            continue

        fm = SHL_FIELD_RE.match(line)
        if fm:
            field, value = fm.group(1), fm.group(2).strip()
            value_clean = value if value and value not in ('בהמשך', 'TBD') else ''
            if field == 'רעיון':
                current['title'] = value_clean
                current['pillar'] = value_clean  # mirror title as pillar
                last_field = 'title'
            elif field.startswith('ויז'):
                current['visuals']['a'] = value_clean
                last_field = 'visuals'
            elif field.startswith('קופי ויז'):
                current['copy_on_visual']['a'] = value_clean
                last_field = 'copy_on_visual'
            elif field == 'קופי נלווה':
                if value_clean: current['captions']['a'] = value_clean
                last_field = 'caption'
            elif field == 'הסבר':
                current['explanation'] = value_clean
                last_field = 'explanation'
            elif field == 'מקור':
                current['source'] = value_clean
                last_field = 'source'
            continue

        # Continuation of last field
        if last_field == 'title' and not current.get('explanation'):
            current['explanation'] = line
        elif last_field == 'visuals' and current['visuals']['a']:
            current['visuals']['a'] += ' ' + line
        elif last_field == 'copy_on_visual' and current['copy_on_visual']['a']:
            current['copy_on_visual']['a'] += ' ' + line
        elif last_field == 'caption' and current['captions'].get('a'):
            current['captions']['a'] += ' ' + line
        elif last_field == 'explanation':
            current['explanation'] = (current.get('explanation','') + ' ' + line).strip()

    if current: items.append(current)
    return items


# ============================================================================
# NUMBERED FORMAT (`1. title text` / `1) title text` - simplest case)
# ============================================================================

NUM_RE = re.compile(r'^(\d+)[.)]\s+(.+)$')


def parse_numbered(lines: list[str]) -> list[dict]:
    items, current = [], None
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        m = NUM_RE.match(line)
        if m:
            if current: items.append(current)
            current = _empty_item(int(m.group(1)))
            current['title'] = m.group(2).strip()
            current['pillar'] = m.group(2).strip()
            continue
        if current is not None:
            # Append continuation text to explanation
            current['explanation'] = (current.get('explanation','') + ' ' + line).strip()
    if current: items.append(current)
    return items


# ============================================================================
# UNKNOWN FORMAT - graceful degradation
# ============================================================================

def parse_unknown(lines: list[str]) -> list[dict]:
    """Last resort: treat the document as a single block, return one item to
    signal to the user that manual structuring is needed."""
    text = '\n'.join(l for l in lines if l.strip()).strip()
    if not text:
        return []
    return [{
        **_empty_item(1),
        'title': '[פורמט לא מזוהה - נדרשת התערבות ידנית]',
        'pillar': 'לא מזוהה',
        'explanation': text[:1000],
    }]


# ============================================================================
# SHARED
# ============================================================================

def _empty_item(num: int) -> dict:
    return {
        'num': num,
        'date': None,      # None = needs Smart Placement
        'day': None,
        'pillar': '',
        'title': '',
        'explanation': '',
        'source': '',
        'visuals': {'a': '', 'b': ''},
        'copy_on_visual': {'a': '', 'b': ''},
        'captions': {'a': '', 'b': ''},
        'status': 'בעבודה',
    }


def normalize_date(s: str | None) -> str | None:
    if not s: return None
    parts = s.split('.')
    if len(parts) != 3: return None
    d, m, y = parts
    y = int(y)
    if y < 100: y += 2000
    return f'{y:04d}-{int(m):02d}-{int(d):02d}'


TYPE_CANONICAL = {
    'רייל': 'reel', 'רילס': 'reel', 'סרטון': 'reel', 'reel': 'reel',
    'קרוסלה': 'carousel', 'carousel': 'carousel',
    'סטורי': 'story', 'סטוריז': 'story', 'story': 'story', 'stories': 'story',
}
TYPE_LABEL = {'post': 'פוסט', 'carousel': 'קרוסלה', 'story': 'סטורי', 'reel': 'רילס'}


def classify_type(raw: str) -> str:
    if not raw: return 'post'
    low = raw.lower()
    for key, val in TYPE_CANONICAL.items():
        if key in low or key in raw:
            return val
    return 'post'


META_INTRO_PREFIXES = (
    'פתיחת הסדרה', 'סגירת הסדרה', 'פינה חדשה', 'הרייל הראשון',
    'הרייל ה', 'הפוסט הראשון', 'פוסט אדווקסי', 'פתיחת ה',
)


def extract_short_and_source(full_explanation: str) -> tuple[str, str]:
    if not full_explanation:
        return '', ''
    text = full_explanation.strip()
    src_lines, cleaned_lines = [], []
    for line in text.split('\n'):
        ls = line.strip()
        if ls.startswith('מקור:') or ls.startswith('מקורות:'):
            src_lines.append(ls.split(':', 1)[1].strip() if ':' in ls else ls)
        else:
            cleaned_lines.append(line)
    source = ' | '.join(src_lines) if src_lines else ''

    body = '\n'.join(cleaned_lines).strip()
    if not body:
        return '', source

    first_para = body.split('\n\n')[0].strip()
    sentences = re.split(r'(?<=[.!?])\s+', first_para)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return '', source

    skip = 0
    while skip < len(sentences) and any(sentences[skip].startswith(p) for p in META_INTRO_PREFIXES):
        skip += 1
    if skip >= len(sentences):
        skip = 0

    short = sentences[skip]
    if skip + 1 < len(sentences) and len(short) < 100:
        short = (short + ' ' + sentences[skip + 1]).strip()
    if len(short) > 200:
        short = short[:197].rstrip() + '...'
    return short, source


# ============================================================================
# DISPATCHER
# ============================================================================

PARSERS = {
    'adavot': parse_adavot,
    'shlichut_horaa': parse_shlichut_horaa,
    'numbered': parse_numbered,
    'unknown': parse_unknown,
}


def parse_file(path: Path, force_format: str | None = None) -> tuple[list[dict], str]:
    lines = extract_lines(path)
    fmt = force_format or detect_format(lines)
    parser = PARSERS.get(fmt, parse_unknown)
    items = parser(lines)
    return items, fmt


def enrich_items(items: list[dict]) -> None:
    """In-place: add date_iso, type_key, type_label, pillar_label, short_explanation, source."""
    for it in items:
        it['date_iso'] = normalize_date(it.get('date'))
        it['type_key'] = classify_type(it.get('pillar', ''))
        it['type_label'] = TYPE_LABEL[it['type_key']]
        pillar = it.get('pillar', '') or ''
        it['pillar_label'] = pillar.rsplit('#', 1)[0].strip().rstrip('-').strip() or pillar
        # Only auto-extract short/source if not already set (Shlichut parser sets source directly)
        if not it.get('short_explanation'):
            short, source = extract_short_and_source(it.get('explanation', ''))
            it['short_explanation'] = short
            if source and not it.get('source'):
                it['source'] = source


# ============================================================================
# MAIN
# ============================================================================

def main():
    ap = argparse.ArgumentParser(description='Parse a Gantt document → structured JSON')
    ap.add_argument('input', help='Path to .docx / .pdf / .txt / .md')
    ap.add_argument('--out', required=True, help='Path to output JSON')
    ap.add_argument('--client', required=True, help='Client name (Hebrew)')
    ap.add_argument('--period', required=True, help='e.g. "יוני 2026" or "20.5-30.6.2026"')
    ap.add_argument('--format', choices=list(PARSERS.keys()), help='Force a specific format')
    args = ap.parse_args()

    items, fmt = parse_file(Path(args.input), args.format)
    enrich_items(items)

    needs_placement = [it for it in items if it.get('date_iso') is None]

    out = {
        'client': args.client,
        'period': args.period,
        'count': len(items),
        'detected_format': fmt,
        'needs_placement': len(needs_placement),
        'items': items,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'WROTE {args.out}')
    print(f'  Format detected: {fmt}')
    print(f'  Items: {len(items)}')
    print(f'  Needs placement (missing dates): {len(needs_placement)}')
    for it in items[:5]:
        date_str = it.get('date_iso') or '???'
        print(f"  #{it['num']:>2} {date_str} [{it['type_key']}] {it.get('title','')[:50]}")
    if needs_placement:
        print()
        print('⚠ Run smart_placement.py to propose dates before build.py')


if __name__ == '__main__':
    main()
