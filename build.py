# -*- coding: utf-8 -*-
"""
Build V4: data.json -> index.html.

Premium dark mode monthly Gantt viewer for Seliger Shomron clients.
- One month per view, tabs between months
- 3 content types only (post / story / reel) drive color
- Rubik (Hebrew) + Inter (English/digits)
- Generous breathing room
- Modal: editable copy (right) + image dropzone (left), localStorage persistence
- Status dropdown per cell with localStorage persistence
"""
import sys, io, json, html, argparse, base64, calendar
from datetime import date
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pyluach.dates import GregorianDate


# 4 content types - cool family (cyan/teal/lavender/rose)
TYPE_COLORS = {
    'post':     {'accent': '#67E8F9', 'soft': 'rgba(103,232,249,0.14)', 'label': 'פוסט'},
    'carousel': {'accent': '#5EEAD4', 'soft': 'rgba(94,234,212,0.14)',  'label': 'קרוסלה'},
    'story':    {'accent': '#C4B5FD', 'soft': 'rgba(196,181,253,0.14)', 'label': 'סטורי'},
    'reel':     {'accent': '#FDA4AF', 'soft': 'rgba(253,164,175,0.14)', 'label': 'רילס'},
}

# Statuses - distinct hues that stay visible on light tray
STATUS_COLORS = {
    'בעבודה':       '#3B82F6',  # blue (active / in-progress)
    'בעיצוב':       '#F97316',  # orange (in design)
    'ממתין לאישור': '#EAB308',  # yellow (waiting)
    'אושר':          '#22C55E',  # green (approved)
}

STATUS_ORDER = ['בעבודה', 'בעיצוב', 'ממתין לאישור', 'אושר']

HEB_WEEKDAYS = ['ראשון','שני','שלישי','רביעי','חמישי','שישי','שבת']

# Hebrew names for Gregorian months
HEB_GREG_MONTHS = ['','ינואר','פברואר','מרץ','אפריל','מאי','יוני',
                   'יולי','אוגוסט','ספטמבר','אוקטובר','נובמבר','דצמבר']

# Holidays are computed dynamically per period via israeli_holidays.get_israeli_holidays()
# This dict is populated at build time in main()
HOLIDAYS_2026 = {}


def heb_date(d: date) -> tuple[str, str]:
    gd = GregorianDate(d.year, d.month, d.day)
    hd = gd.to_heb()
    full = hd.hebrew_date_string()
    parts = full.split()
    return parts[0], full


def build_month_grid(year: int, month: int, items_by_date: dict) -> list:
    cal = calendar.Calendar(firstweekday=6)
    weeks = []
    for week_dates in cal.monthdatescalendar(year, month):
        row = []
        for d in week_dates:
            heb_short, heb_full = heb_date(d)
            iso = d.isoformat()
            cell = {
                'iso': iso,
                'day_num': d.day,
                'weekday': d.weekday(),
                'heb_short': heb_short,
                'heb_full': heb_full,
                'is_outside': d.month != month,
                'is_friday': d.weekday() == 4,
                'is_saturday': d.weekday() == 5,
                'holiday': HOLIDAYS_2026.get(iso, ''),
                'items': items_by_date.get(iso, []),
            }
            row.append(cell)
        weeks.append(row)
    return weeks


def render_cell(cell: dict) -> str:
    classes = ['cell']
    if cell['is_outside']:
        classes.append('outside')
        cell = {**cell, 'items': [], 'holiday': ''}
    if cell['is_friday']:
        classes.append('friday')
    if cell['is_saturday']:
        classes.append('saturday')
    if cell['holiday']:
        classes.append('holiday')
    if cell['items']:
        classes.append('has-content')
        primary = cell['items'][0]
        classes.append(f"type-{primary['type_key']}")

    header_parts = [
        f'<div class="cell-num">{cell["day_num"]}</div>',
        f'<div class="cell-heb">{html.escape(cell["heb_short"])}</div>',
    ]
    if cell['holiday']:
        header_parts.append(f'<div class="cell-hol">{html.escape(cell["holiday"])}</div>')

    body_parts = []
    for it in cell['items']:
        tc = TYPE_COLORS.get(it['type_key'], TYPE_COLORS['post'])
        pillar = html.escape(it.get('pillar_label', ''))
        title = html.escape(it['title'])
        type_label = html.escape(tc['label'])
        # Warning if content placed on Shabbat or holiday
        warning = ''
        if cell.get('is_saturday') or cell.get('holiday'):
            warning = '<span class="cell-warning" title="תוכן זה ממוקם בשבת/חג - שקול להעביר לערב חג / יום שישי">⚠</span>'
        body_parts.append(f'''
        <div class="cell-type-row">
          <span class="cell-type-chip">{type_label}</span>
          {warning}
        </div>
        <div class="cell-title">{title}</div>
        <div class="cell-footer">
          <div class="cell-status-row">
            <span class="cell-status-label">סטטוס:</span>
            <select class="cell-status" data-num="{it['num']}" aria-label="סטטוס" onclick="event.stopPropagation()">
              __STATUS_OPTS_{it['num']}__
            </select>
          </div>
          <button class="cell-open" data-num="{it['num']}">צפייה ←</button>
        </div>''')

    draggable_attr = 'draggable="true"' if cell['items'] and not cell['is_outside'] else ''
    return f'''<div class="{' '.join(classes)}" data-iso="{cell['iso']}" {draggable_attr}>
      <div class="cell-head">{''.join(header_parts)}</div>
      <div class="cell-body">{''.join(body_parts)}</div>
    </div>'''


def render_month(year: int, month: int, items_by_date: dict, is_active: bool) -> str:
    weeks = build_month_grid(year, month, items_by_date)
    head_cells = ''.join(f'<div class="wd">{wd}</div>' for wd in HEB_WEEKDAYS)
    rows_html = []
    for week in weeks:
        rows_html.append('<div class="week">' + ''.join(render_cell(c) for c in week) + '</div>')
    active_cls = ' active' if is_active else ''
    return f'''
    <section class="month{active_cls}" data-month="{year}-{month:02d}">
      <div class="weekdays">{head_cells}</div>
      <div class="grid">{''.join(rows_html)}</div>
    </section>
    '''


def render_status_opts_for_items(html_str: str, items: list) -> str:
    """Inject <option> sets per item into the rendered cell HTML."""
    for it in items:
        status = it.get('status', 'בעבודה')
        opts = ''.join(
            f'<option value="{html.escape(s)}"{" selected" if s == status else ""}>{html.escape(s)}</option>'
            for s in STATUS_ORDER
        )
        html_str = html_str.replace(f"__STATUS_OPTS_{it['num']}__", opts)
    return html_str


def render_legend() -> str:
    type_chips = ''.join(
        f'<span class="legend-chip"><span class="sw" style="background:{v["accent"]};"></span>{html.escape(v["label"])}</span>'
        for v in TYPE_COLORS.values()
    )
    status_chips = ''.join(
        f'<span class="legend-chip"><span class="sw round" style="background:{c}; box-shadow:0 0 6px {c}80;"></span>{html.escape(s)}</span>'
        for s, c in STATUS_COLORS.items()
    )
    return f'''
    <div class="legend">
      <div class="legend-group">
        <span class="legend-label">סוג תוכן</span>
        {type_chips}
      </div>
      <div class="legend-divider"></div>
      <div class="legend-group">
        <span class="legend-label">סטטוס</span>
        {status_chips}
      </div>
    </div>
    '''


def render_tabs(months: list) -> str:
    """Render month picker as a left-side dropdown (kept name for compatibility).
    Default = first month (chronological). Arrow indicates dropdown.
    """
    if not months:
        return ''
    opts = []
    for i, (y, m) in enumerate(months):
        title = f'{HEB_GREG_MONTHS[m]} {y}'
        selected = ' selected' if i == 0 else ''
        opts.append(f'<option value="{y}-{m:02d}"{selected}>{title}</option>')
    return (
        '<div class="month-picker">'
        '<span class="month-picker-label">חודש</span>'
        f'<select class="month-select" aria-label="בחר חודש">{"".join(opts)}</select>'
        '<svg class="month-picker-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>'
        '</div>'
    )


def render_modal_data(items: list) -> str:
    slim = []
    for it in items:
        tc = TYPE_COLORS.get(it['type_key'], TYPE_COLORS['post'])
        slim.append({
            'num': it['num'],
            'date': it['date_iso'],
            'day': it['day'],
            'type_key': it['type_key'],
            'type_label': tc['label'],
            'type_accent': tc['accent'],
            'type_soft': tc['soft'],
            'title': it['title'],
            'short_explanation': it.get('short_explanation', ''),
            'source': it.get('source', ''),
            'status': it['status'],
        })
    return json.dumps(slim, ensure_ascii=False)


THEME_TOKENS = {
    'zeliger': {
        'bg': '#07101F', 'paper': '#0F1A2E', 'paper-2': '#14223A',
        'paper-3': '#0C1828', 'paper-4': '#18253F',
        'ink': '#F1F5F9', 'ink-soft': '#94A3B8', 'ink-faint': '#475569', 'ink-mute': '#64748B',
        'border': '#1E2D45', 'border-soft': '#182338',
        'accent-primary': '#67E8F9', 'accent-secondary': '#A78BFA', 'accent-warm': '#FB7185',
        'gold': '#FBBF24',
        'shadow-sm': '0 1px 2px rgba(0,0,0,0.3)',
        'shadow-md': '0 4px 20px rgba(0,0,0,0.35)',
        'shadow-lg': '0 20px 60px rgba(0,0,0,0.5)',
        'font-he': "'Rubik', system-ui, -apple-system, sans-serif",
        'font-en': "'Inter', system-ui, -apple-system, sans-serif",
        'font': "'Inter', 'Rubik', system-ui, sans-serif",
    },
    'uria': {
        # Uria Berman brand kit - DARK aubergine mode
        # Inspired by brand kit's hero banner: linear-gradient(135deg, #4C1D95 0%, #1A1A1A 100%)
        # CRITICAL FONT RULE: Hebrew = Rubik, English/digits = Plus Jakarta Sans
        'bg': '#0A0418',          # Ink-aubergine deep (almost black with purple tint)
        'paper': '#160730',       # Card surface - dark aubergine
        'paper-2': '#1F0E45',     # Slightly lighter aubergine for cells
        'paper-3': '#120524',     # Weekend cell - darker
        'paper-4': '#250F50',     # Saturday slightly stronger
        'ink': '#FAFAFA',         # Paper white text
        'ink-soft': '#C4B5FD',    # Lavender for secondary text
        'ink-faint': '#5B4685',   # Faded purple
        'ink-mute': '#8B7BA5',    # Muted purple
        'border': '#2D1759',      # Aubergine border
        'border-soft': '#1F0E45',
        'accent-primary': '#A78BFA',    # Lighter aubergine (visible on dark)
        'accent-secondary': '#22D3EE',  # Brighter teal (visible on dark)
        'accent-warm': '#FF8A65',       # Lighter tangerine
        'gold': '#FF8A65',              # Tangerine holiday
        'shadow-sm': '0 1px 2px rgba(0,0,0,0.4)',
        'shadow-md': '0 4px 20px rgba(0,0,0,0.5)',
        'shadow-lg': '0 20px 60px rgba(0,0,0,0.7)',
        'font-he': "'Rubik', 'Heebo', sans-serif",
        'font-en': "'Plus Jakarta Sans', sans-serif",
        'font': "'Rubik', 'Heebo', sans-serif",
    },
}


def render_theme_root(mode: str) -> str:
    """Build the :root { ... } CSS block for the chosen mode."""
    t = THEME_TOKENS.get(mode, THEME_TOKENS['zeliger'])
    lines = ['  /* Theme: ' + mode + ' */']
    lines.append(f"  --bg:        {t['bg']};")
    lines.append(f"  --paper:     {t['paper']};")
    lines.append(f"  --paper-2:   {t['paper-2']};")
    lines.append(f"  --paper-3:   {t['paper-3']};")
    lines.append(f"  --paper-4:   {t['paper-4']};")
    lines.append(f"  --ink:       {t['ink']};")
    lines.append(f"  --ink-soft:  {t['ink-soft']};")
    lines.append(f"  --ink-faint: {t['ink-faint']};")
    lines.append(f"  --ink-mute:  {t['ink-mute']};")
    lines.append(f"  --border:    {t['border']};")
    lines.append(f"  --border-soft: {t['border-soft']};")
    lines.append(f"  --accent-cyan: {t['accent-primary']};")
    lines.append(f"  --accent-primary: {t['accent-primary']};")
    lines.append(f"  --accent-secondary: {t['accent-secondary']};")
    lines.append(f"  --accent-warm: {t['accent-warm']};")
    lines.append(f"  --gold:      {t['gold']};")
    lines.append(f"  --shadow-sm: {t['shadow-sm']};")
    lines.append(f"  --shadow-md: {t['shadow-md']};")
    lines.append(f"  --shadow-lg: {t['shadow-lg']};")
    lines.append(f"  --font-he: {t['font-he']};")
    lines.append(f"  --font-en: {t['font-en']};")
    lines.append(f"  --font: {t['font']};")
    return ':root {\n' + '\n'.join(lines) + '\n}'


# Uria-mode overrides: light-theme specific rules that flip the dark-mode hardcoded overlays
URIA_OVERRIDES = '''
/* Uria DARK mode - FLAT aubergine tint on dark (no gradients - brand rule) */
body.theme-uria .cell.has-content {
  background: rgba(167,139,250,0.10) !important;
  border-color: rgba(167,139,250,0.40) !important;
  box-shadow:
    0 1px 0 rgba(255,255,255,0.04) inset,
    0 4px 16px rgba(0,0,0,0.4) !important;
}
body.theme-uria .cell.has-content:hover {
  background: rgba(167,139,250,0.16) !important;
  border-color: rgba(167,139,250,0.65) !important;
}
body.theme-uria .cell-footer {
  background: rgba(10,4,24,0.45) !important;        /* Solid dark band, full cell width */
  border-top: 1px solid rgba(255,255,255,0.10) !important;
  border-radius: 0 !important;
}
body.theme-uria .cell-open {
  background: #22D3EE !important;     /* Bright teal on dark */
  border-color: #22D3EE !important;
  color: #0A0418 !important;          /* Dark text on teal button */
}
body.theme-uria .cell-open:hover {
  background: #FF8A65 !important;     /* Tangerine on hover */
  border-color: #FF8A65 !important;
  color: #0A0418 !important;
}
/* Uria today: TANGERINE ring + tangerine badge (per user request) */
body.theme-uria .cell.is-today {
  border: 2px solid #FF6B35 !important;
  box-shadow:
    0 0 0 4px rgba(255,107,53,0.18),
    0 0 0 1px #FF6B35 inset,
    0 0 36px rgba(255,107,53,0.45) !important;
  outline: 1px solid rgba(255,107,53,0.65);
  outline-offset: 2px;
}
body.theme-uria .cell.is-today .cell-num { color: #FF6B35 !important; }
body.theme-uria .cell.is-today::after {
  background: #FF6B35;
  color: #FFFFFF;
  box-shadow: 0 2px 8px rgba(255,107,53,0.45);
  font-family: 'Rubik', sans-serif;  /* Hebrew text - must be Rubik */
}
@keyframes uria-today-pulse {
  0%, 100% { box-shadow: 0 0 0 2px #FF6B35, 0 0 24px rgba(255,107,53,0.40); }
  50% { box-shadow: 0 0 0 2px #FF6B35, 0 0 40px rgba(255,107,53,0.70); }
}
body.theme-uria .cell.is-today { animation: uria-today-pulse 2.5s ease-in-out infinite; }
body.theme-uria .cell.holiday::before {
  border-color: #FF6B35 transparent transparent transparent;
}
body.theme-uria .cell-status-label { color: #FAFAFA; }
body.theme-uria .header-brand { filter: none; }
body.theme-uria .modal {
  background: #160730;
  border-color: #2D1759;
  color: #FAFAFA;
}
body.theme-uria .modal-bg { background: rgba(10,4,24,0.85); backdrop-filter: blur(10px); }
body.theme-uria .modal-head { background: #160730; border-bottom-color: #2D1759; }
body.theme-uria .modal-head-left h2 { color: #FAFAFA; }
body.theme-uria .modal-head-left .date-row { color: #C4B5FD; }
body.theme-uria .modal-head-left .date-row .dot { background: #5B4685; }
body.theme-uria .modal-explainline {
  background: rgba(34,211,238,0.08);
  border-right: 3px solid #22D3EE;
  color: #FAFAFA;
}
body.theme-uria .modal-source { color: #C4B5FD; }
body.theme-uria .modal-source-label { color: #8B7BA5; }
body.theme-uria .copy-area textarea {
  background: #0A0418;
  border-color: #2D1759;
  color: #FAFAFA;
}
body.theme-uria .copy-area textarea:focus { border-color: #A78BFA; }
body.theme-uria .copy-area textarea::placeholder { color: #5B4685; }
body.theme-uria .copy-area label { color: #C4B5FD; }
body.theme-uria .copy-view {
  background: #0A0418;
  border-color: #2D1759;
  color: #FAFAFA;
}
body.theme-uria .dropzone {
  background: #0A0418;
  border-color: #2D1759;
}
body.theme-uria .dropzone:hover {
  border-color: #A78BFA;
  background: rgba(167,139,250,0.06);
}
body.theme-uria .dropzone .dz-icon { color: #5B4685; }
body.theme-uria .dropzone .dz-text { color: #C4B5FD; }
body.theme-uria .dropzone .dz-sub { color: #8B7BA5; }
body.theme-uria .copy-save-btn {
  background: #22D3EE;
  border-color: #22D3EE;
  color: #0A0418;
}
body.theme-uria .copy-save-btn:hover { background: #67E8F9; border-color: #67E8F9; }
body.theme-uria .copy-save-btn.saved-flash { background: #A78BFA; border-color: #A78BFA; color: #0A0418; }
body.theme-uria .copy-save-btn.is-dirty { background: #FF8A65; border-color: #FF8A65; color: #0A0418; }
body.theme-uria .pair-item {
  background: #0A0418;
  border-color: #2D1759;
  color: #FAFAFA;
}
body.theme-uria .pair-item .pair-text { color: #FAFAFA; }
body.theme-uria .modal-close {
  background: rgba(167,139,250,0.15);
  border-color: #2D1759;
  color: #C4B5FD;
}
body.theme-uria .modal-close:hover {
  background: rgba(167,139,250,0.30);
  color: #FAFAFA;
}
body.theme-uria .modal-section h3 {
  color: #C4B5FD;
  border-bottom-color: #2D1759;
}
body.theme-uria .explanation { color: #C4B5FD; }
body.theme-uria details.collapsible {
  background: #0A0418;
  border-color: #2D1759;
}
body.theme-uria details.collapsible > summary { color: #FAFAFA; }
body.theme-uria details.collapsible > summary::after { color: #C4B5FD; }
body.theme-uria .pair-label { color: #C4B5FD; }
/* Uria month-picker (dark) */
body.theme-uria .month-picker {
  background: rgba(34,211,238,0.06);
  border: 1px solid rgba(34,211,238,0.30);
}
body.theme-uria .month-picker:hover {
  border-color: #22D3EE;
  box-shadow: 0 0 0 1px #22D3EE, 0 0 18px rgba(34,211,238,0.25);
}
body.theme-uria .month-picker-label { color: #C4B5FD; }
body.theme-uria .month-select { color: #FAFAFA; }
body.theme-uria .month-select option { background: #160730; color: #FAFAFA; }
body.theme-uria .month-picker-arrow { color: #22D3EE; }
body.theme-uria .share-btn {
  color: #0A0418;                         /* Dark text on FLAT tangerine */
  background: #FF6B35;                    /* Brand tangerine - solid */
  border-color: #FF6B35;
  font-weight: 800;
}
body.theme-uria .share-btn:hover {
  background: #FF8A65;
  border-color: #FF8A65;
}
body.theme-uria .pdf-btn {
  color: #FF6B35;                         /* Tangerine outline variant for contrast */
  background: rgba(255,107,53,0.06);
  border-color: rgba(255,107,53,0.50);
  font-weight: 800;
}
body.theme-uria .pdf-btn:hover {
  background: rgba(255,107,53,0.18);
  border-color: #FF6B35;
}
body.theme-uria .h1-label { color: #FAFAFA; background: transparent; padding: 0; }
body.theme-uria .header-titles .count-pill {
  color: #A78BFA;
  background: rgba(167,139,250,0.10);
  border-color: rgba(167,139,250,0.30);
}
body.theme-uria .cell.friday { background: #120524; }
body.theme-uria .cell.saturday {
  background: #160730;
  border-color: rgba(255,138,101,0.15);
}
/* Uria DARK mode: type chips - bright on dark with contrast */
body.theme-uria .cell.type-post .cell-type-chip {
  background: #A78BFA !important;  /* Bright aubergine */
  color: #0A0418 !important;
}
body.theme-uria .cell.type-carousel .cell-type-chip {
  background: #22D3EE !important;  /* Bright teal */
  color: #0A0418 !important;
}
body.theme-uria .cell.type-story .cell-type-chip {
  background: #FF8A65 !important;  /* Bright tangerine */
  color: #0A0418 !important;
}
body.theme-uria .cell.type-reel .cell-type-chip {
  background: #C4B5FD !important;  /* Lavender (lighter aubergine) */
  color: #0A0418 !important;
}

/* Uria DARK: FLAT cell tints by type (brand rule = no gradients) */
body.theme-uria .cell.type-post {
  background: rgba(167,139,250,0.12) !important;
  border-color: rgba(167,139,250,0.45) !important;
  box-shadow: 0 4px 18px rgba(0,0,0,0.35) !important;
}
body.theme-uria .cell.type-carousel {
  background: rgba(34,211,238,0.12) !important;
  border-color: rgba(34,211,238,0.45) !important;
  box-shadow: 0 4px 18px rgba(0,0,0,0.35) !important;
}
body.theme-uria .cell.type-story {
  background: rgba(255,138,101,0.12) !important;
  border-color: rgba(255,138,101,0.45) !important;
  box-shadow: 0 4px 18px rgba(0,0,0,0.35) !important;
}
body.theme-uria .cell.type-reel {
  background: rgba(196,181,253,0.10) !important;
  border-color: rgba(196,181,253,0.40) !important;
  box-shadow: 0 4px 18px rgba(0,0,0,0.35) !important;
}

/* Uria logo - Logo 03 (אוריה ברמן. with colored period) per brand kit final-3.html */
body.theme-uria .uria-x-logo {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}
body.theme-uria .uria-x-logo .logo-name-block {
  display: inline-flex;
  align-items: baseline;
  font-family: 'Rubik', 'Heebo', sans-serif;
  font-weight: 900;
  font-size: 32px;
  letter-spacing: -0.04em;
  line-height: 1;
  color: #FAFAFA;          /* White text on dark aubergine bg */
}
body.theme-uria .uria-x-logo .logo-period {
  color: #FF8A65;          /* Tangerine period */
  margin-right: 3px;       /* Proper spacing from ן */
  font-family: 'Rubik', 'Heebo', sans-serif;
  font-size: 36px;
  line-height: 1;
}
body.theme-uria .uria-x-logo .logo-tagline {
  display: inline-block;
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 11px;            /* Larger and consistent */
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #22D3EE;             /* Teal blue tagline (brand kit secondary) */
}
body.theme-uria .uria-x-logo .logo-tagline .tag-accent {
  color: #22D3EE;             /* AI in matching teal */
  font-size: 11px;
  font-weight: 800;
}

/* Uria header in NEGATIVE - dark aubergine bg with light text on top */
body.theme-uria .header {
  position: relative;
  border: none;
  background: #0A0418 !important;            /* FLAT dark aubergine - brand rule = no gradient */
  box-shadow: 0 4px 18px rgba(0,0,0,0.55);
  color: #FAFAFA;
  overflow: hidden;
}
/* Kill the cyan accent strip + cyan tint that Zeliger uses; Uria stays flat */
body.theme-uria .header::before {
  display: none !important;
}
body.theme-uria .header-titles h1 {
  font-family: 'Rubik', 'Heebo', sans-serif;
  font-weight: 900;
  letter-spacing: -0.03em;
  color: #FAFAFA;
}
body.theme-uria .h1-label {
  background: transparent !important;
  color: #FAFAFA !important;
  padding: 0 !important;
  font-family: 'Rubik', sans-serif;
  font-size: 26px;
  font-weight: 900;
  letter-spacing: -0.02em;
}
body.theme-uria .h1-sep {
  display: inline-flex !important;
  align-items: center;
  justify-content: center;
  width: auto !important;
  height: auto !important;
  background: transparent !important;
  box-shadow: none !important;
  margin: 0 8px !important;
}
body.theme-uria .h1-sep .x-box-mini {
  display: inline-block;
  background: transparent;
  color: #FF6B35;             /* Brand tangerine × — bigger, playful */
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-weight: 900;
  font-size: 40px;            /* Big and fun (was 24) */
  line-height: 0.7;
  letter-spacing: 0;
  transform: translateY(2px);
  transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}
body.theme-uria .h1-sep .x-box-mini:hover {
  transform: translateY(2px) rotate(90deg);
}
body.theme-uria .h1-client {
  color: #FAFAFA;
  font-weight: 900;
  font-size: 26px;
  margin-right: 4px;
}
body.theme-uria .header-titles .period {
  font-family: 'Plus Jakarta Sans', sans-serif;
  color: #C4B5FD;
  font-weight: 600;
}
body.theme-uria .header-titles .hint {
  font-family: 'Rubik', sans-serif;
  color: #8B7BA5;
}

/* Uria footer - FLAT dark strip with English brand name + × separator (brand rule = no gradient) */
body.theme-uria .footer {
  background: #0A0418;
  color: #FAFAFA;
  padding: 16px 22px;
  margin-top: 18px;
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  border-top: 2px solid #FF6B35;   /* Tangerine accent line */
}
body.theme-uria .footer-built {
  color: #C4B5FD;
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-weight: 700;
  letter-spacing: 0.18em;
}
body.theme-uria .footer-x {
  display: inline-block;
  background: transparent;
  color: #FF6B35;
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-weight: 900;
  font-size: 20px;
  line-height: 1;
  margin: 0 2px;
}
body.theme-uria .footer-brand {
  font-family: 'Plus Jakarta Sans', sans-serif;
  color: #FAFAFA;
  font-weight: 900;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-size: 14px;
}
body.theme-uria .footer-period {
  display: inline-block;
  color: #FF6B35;
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-weight: 900;
  font-size: 18px;
  line-height: 0.6;
  margin-left: -10px;            /* Pull the dot snug to "Berman" — fix wide gap */
  margin-right: 0;
}

/* (Uria month-picker overrides defined earlier in this file) */

/* Type chips Uria - HEBREW text = Rubik. NOT Plus Jakarta. */
body.theme-uria .cell-type-chip {
  font-family: 'Rubik', sans-serif !important;
  font-weight: 700 !important;
  font-size: 10px !important;
  letter-spacing: 0 !important;
  text-transform: none !important;
  border-radius: 999px !important;
  padding: 2px 10px !important;
  box-shadow: none !important;
}

/* Title text in cells - WHITE on dark, Hebrew = Rubik */
body.theme-uria .cell-title {
  color: #FAFAFA !important;
  font-weight: 700 !important;
  font-family: 'Rubik', sans-serif !important;
}

/* Status label HEBREW = Rubik, light on dark */
body.theme-uria .cell-status-label {
  font-family: 'Rubik', sans-serif;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: none;
  font-size: 10px;
  color: #FAFAFA;
}
body.theme-uria .cell-status {
  font-family: 'Rubik', sans-serif;  /* Status values are Hebrew */
  font-weight: 700;
  letter-spacing: 0;
}

/* Legend strip Uria - dark mode */
body.theme-uria .legend {
  background: #160730;
  border: 1px solid #2D1759;
  border-radius: 0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.4);
}
body.theme-uria .legend-label {
  font-family: 'Rubik', sans-serif;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: none;
  font-size: 11px;
  color: #A78BFA;
  background: rgba(167,139,250,0.10);
}
body.theme-uria .legend-divider { background: #2D1759; }
body.theme-uria .legend-chip {
  font-family: 'Rubik', sans-serif;
  font-weight: 600;
  color: #FAFAFA;
}

/* Weekday headers - light on dark */
body.theme-uria .wd {
  font-family: 'Rubik', sans-serif;
  font-weight: 600;
  letter-spacing: 0;
  text-transform: none;
  color: #C4B5FD;
  font-size: 11px;
}

/* Month wrap - dark */
body.theme-uria .month {
  background: #160730;
  border: 1px solid #2D1759;
  border-radius: 0;
  box-shadow: 0 4px 18px rgba(0,0,0,0.5);
}

/* Cell empty (no content) background */
body.theme-uria .cell:not(.has-content):not(.outside) {
  background: rgba(255,255,255,0.02);
  border-color: #2D1759;
}

/* Cell number = Plus Jakarta (number), light color */
body.theme-uria .cell-num {
  color: #FAFAFA !important;
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-weight: 900;
}
/* Hebrew date letter = Rubik */
body.theme-uria .cell-heb {
  color: #A78BFA !important;
  font-family: 'Rubik', sans-serif !important;
  font-weight: 700;
}
/* Outside cells (other month) - more dim on dark */
body.theme-uria .cell.outside .cell-num,
body.theme-uria .cell.outside .cell-heb {
  color: #3D2A6A !important;
}
body.theme-uria .cell.outside { border-color: transparent !important; }
/* Holiday label in cell = Hebrew = Rubik */
body.theme-uria .cell-hol {
  font-family: 'Rubik', sans-serif !important;
  font-weight: 700;
  color: #FF6B35;
}
/* Share button hint = Hebrew = Rubik */
body.theme-uria .share-btn {
  font-family: 'Rubik', sans-serif;
  font-weight: 700;
}
body.theme-uria .restore-btn {
  font-family: 'Rubik', sans-serif;
  font-weight: 700;
}
/* Open cell button = Hebrew "צפייה" = Rubik */
body.theme-uria .cell-open {
  font-family: 'Rubik', sans-serif !important;
  font-weight: 700 !important;
  letter-spacing: 0 !important;
}
/* Modal headings */
body.theme-uria .modal-head-left h2 {
  font-family: 'Rubik', sans-serif;
}
body.theme-uria .modal-pill {
  font-family: 'Rubik', sans-serif !important;
}
body.theme-uria .modal-explainline {
  font-family: 'Rubik', sans-serif;
}
body.theme-uria .copy-area label,
body.theme-uria .pair-item .pair-label,
body.theme-uria .modal-section h3 {
  font-family: 'Rubik', sans-serif !important;
  font-weight: 800 !important;
}
'''


CSS = '''
__THEME_ROOT__

* { box-sizing: border-box; }
html, body { margin:0; padding:0; }
body {
  font-family: var(--font);
  direction: rtl;
  background: var(--bg);
  color: var(--ink);
  font-size: 14px;
  line-height: 1.55;
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

.page {
  max-width: 1480px;
  margin: 0 auto;
  padding: 24px 32px 36px;
}

/* TV-DASHBOARD STYLE HEADER (Zeliger): glass panel with cyan accent strip */
.header {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22px 30px;
  gap: 32px;
  background:
    linear-gradient(90deg, rgba(103,232,249,0.07) 0%, rgba(103,232,249,0.02) 50%, transparent 100%),
    var(--paper);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow-md), 0 0 40px rgba(103,232,249,0.04);
  margin-bottom: 16px;
  overflow: hidden;
}
.header::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: linear-gradient(180deg, var(--accent-cyan) 0%, rgba(103,232,249,0.3) 100%);
  box-shadow: 0 0 14px rgba(103,232,249,0.55);
}
.header-meta-label {
  font-family: var(--font-en);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--accent-cyan);
  opacity: 0.85;
}
.header-brand {
  display: flex;
  align-items: center;
  filter: invert(1) hue-rotate(180deg) brightness(1.05);
}
.brand-link {
  display: inline-flex;
  align-items: center;
  text-decoration: none;
  color: inherit;
  cursor: pointer;
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.brand-link:hover { opacity: 0.85; transform: translateY(-1px); }
body.theme-uria .header-brand { filter: none; }
.header img.logo {
  height: 46px;
  width: auto;
  display: block;
}
.header-titles {
  display: flex;
  flex-direction: column;
  align-items: flex-end;          /* In RTL, flex-end = visual LEFT — block hugs left edge */
  gap: 4px;
  flex: 1;
}
.header-titles h1 {
  margin: 0;
  font-family: var(--font-he);
  font-size: 28px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.015em;
  line-height: 1.1;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;                /* Title flows naturally RTL: גאנט חודשי · שליחות הוראה reads right-to-left */
}
.period-mini {
  font-family: var(--font-en);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-mute);
  margin-bottom: 2px;
}
.period-mini .heb {
  font-family: var(--font-he);
  letter-spacing: 0.05em;
  text-transform: none;
  font-weight: 500;
  color: var(--ink-soft);
  margin-inline-start: 6px;
}
.h1-label {
  color: var(--accent-cyan);
  font-weight: 700;
  font-size: 26px;
}
.h1-sep {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 6px;
  height: 6px;
  background: var(--accent-cyan);
  color: transparent;
  font-size: 0;
  border-radius: 2px;
  box-shadow: 0 0 12px rgba(103,232,249,0.55);
  margin: 0 4px;
}
.h1-client { color: var(--ink); font-size: 26px; font-weight: 700; }
.header-titles .period {
  font-family: var(--font-en);
  font-size: 13px;
  color: var(--ink-soft);
  font-weight: 400;
  letter-spacing: 0.02em;
}
.header-titles .hint {
  font-size: 11px;
  color: var(--ink-mute);
  letter-spacing: 0.01em;
}
.header-hint {
  font-family: var(--font-he);
  font-size: 11px;
  color: var(--ink-mute);
  letter-spacing: 0.01em;
  margin-top: 2px;
}
.share-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-he);
  font-size: 12px;
  font-weight: 700;
  color: #FACC15;                         /* Zeliger secondary: yellow */
  background: rgba(250,204,21,0.10);
  border: 1px solid rgba(250,204,21,0.40);
  padding: 6px 14px;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.share-btn:hover {
  background: rgba(250,204,21,0.20);
  border-color: #FACC15;
}
.share-btn.copied {
  background: rgba(34,197,94,0.18);
  border-color: #22C55E;
  color: #22C55E;
}
.restore-btn {
  display: none;
  align-items: center;
  gap: 6px;
  font-family: var(--font-he);
  font-size: 11px;
  font-weight: 600;
  color: #FBBF24;
  background: rgba(251,191,36,0.10);
  border: 1px solid rgba(251,191,36,0.35);
  padding: 5px 12px;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.restore-btn.visible { display: inline-flex; }
.restore-btn:hover {
  background: rgba(251,191,36,0.20);
  border-color: #FBBF24;
}
.header-action-group {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.pdf-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-he);
  font-size: 12px;
  font-weight: 700;
  color: #FACC15;                         /* Zeliger secondary: yellow */
  background: rgba(250,204,21,0.10);
  border: 1px solid rgba(250,204,21,0.40);
  padding: 6px 14px;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.pdf-btn:hover {
  background: rgba(250,204,21,0.20);
  border-color: #FACC15;
}
/* Print styles - PDF download via browser print */
@media print {
  body {
    background: #FFFFFF !important;
    color: #000000 !important;
  }
  .control-cluster, .modal-bg, .modal { display: none !important; }
  .header-hint { display: none !important; }
  .cell.has-content { box-shadow: none !important; border: 1px solid #999 !important; }
  .cell { box-shadow: none !important; }
  .controls { page-break-after: avoid; }
  .month { page-break-inside: avoid; box-shadow: none !important; border: 1px solid #999 !important; }
  .cell-open { display: none; }
  .footer { background: #FFFFFF !important; color: #666 !important; }
}
body.view-mode .restore-btn { display: none !important; }
body.view-mode .cell.has-content { cursor: pointer; }
body.view-mode .cell[draggable] { -webkit-user-drag: none; }
/* In view-mode: hide share/restore buttons + edit hint, show a badge */
body.view-mode .share-btn,
body.view-mode .restore-btn,
body.view-mode .header-hint { display: none !important; }
body.view-mode .control-cluster::before {
  content: 'מצב צפייה · ללא עריכה';
  font-family: var(--font-he);
  font-size: 11px;
  font-weight: 700;
  color: var(--accent-cyan);
  background: rgba(103,232,249,0.08);
  border: 1px solid rgba(103,232,249,0.3);
  padding: 4px 12px;
  border-radius: 999px;
  margin-inline-end: 6px;
}
body.theme-uria.view-mode .control-cluster::before {
  color: #FF6B35;
  background: rgba(255,107,53,0.08);
  border-color: rgba(255,107,53,0.40);
}
/* In view-mode: hide status dropdown in cells, show as static pill */
body.view-mode .cell-status {
  pointer-events: none;
  appearance: none;
  background-image: none;
  padding-left: 9px;
}

/* CONTROLS ROW: legend (right in RTL) + cluster of action buttons + month-picker (left in RTL) */
.controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.control-cluster {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* MONTH PICKER (dropdown, left side) */
.month-picker {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 6px 12px 6px 14px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.month-picker:hover {
  border-color: var(--accent-cyan);
  box-shadow: 0 0 0 1px var(--accent-cyan), 0 0 16px rgba(103,232,249,0.18);
}
.month-picker-label {
  font-family: var(--font-he);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-mute);
}
.month-select {
  font-family: var(--font-he);
  font-size: 14px;
  font-weight: 700;
  color: var(--ink);
  background: transparent;
  border: none;
  outline: none;
  padding: 4px 4px 4px 0;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
  direction: rtl;
  text-align: right;
  min-width: 110px;
}
.month-select option {
  background: var(--paper);
  color: var(--ink);
  font-family: var(--font-he);
}
.month-picker-arrow {
  color: var(--accent-cyan);
  pointer-events: none;
  flex-shrink: 0;
}

/* LEGEND */
.legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 14px;
  padding: 8px 16px;
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: 999px;
}
.legend-divider {
  width: 1px;
  height: 18px;
  background: var(--border);
}
.legend-group {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.legend-label {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--ink-mute);
  letter-spacing: 0.08em;
  padding: 3px 9px;
  background: rgba(148,163,184,0.08);
  border-radius: 8px;
  text-transform: none;
}
.legend-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--ink);
}
.legend-chip .sw {
  width: 11px;
  height: 11px;
  border-radius: 3px;
}
.legend-chip .sw.round { border-radius: 50%; }

/* MONTH (one at a time via tabs) */
.month {
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 16px 18px 20px;
  box-shadow: var(--shadow-md);
  display: none;
}
.month.active { display: block; }

/* WEEKDAY HEADER */
.weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6px;
  margin-bottom: 6px;
}
.wd {
  text-align: center;
  font-family: var(--font);
  font-size: 11px;
  font-weight: 500;
  color: var(--ink-soft);
  padding: 4px 0 6px;
  letter-spacing: 0.04em;
}

.grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.week {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6px;
}

/* CELL - whole cell is the content card. Type color tints the whole cell. */
.cell {
  position: relative;
  background: var(--paper-2);
  border: 1px solid var(--border);
  border-radius: 10px;
  min-height: 158px;
  padding: 10px 10px 9px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow: hidden;
  transition: all 0.15s ease;
}
.cell:hover {
  border-color: rgba(148,163,184,0.4);
  transform: translateY(-1px);
}

/* Type-tinted cells (content present) */
.cell.has-content {
  cursor: pointer;
}
/* Truly LIT-UP content cells - illuminated CYAN tiles on the dark grid.
   Uniform cyan glow across all content types - differentiation comes from the chip. */
.cell.has-content {
  background:
    linear-gradient(155deg, rgba(103,232,249,0.30) 0%, rgba(103,232,249,0.14) 55%, rgba(103,232,249,0.06) 100%);
  border-color: rgba(103,232,249,0.55);
  box-shadow:
    0 0 0 1px rgba(103,232,249,0.10),
    0 0 32px rgba(103,232,249,0.18),
    0 8px 28px rgba(0,0,0,0.45),
    inset 0 1px 0 rgba(255,255,255,0.14);
}
/* Type accent only via the chip - retain --type-c as CSS var per cell for chip use */
.cell.type-post     { --type-c: #67E8F9; }
.cell.type-carousel { --type-c: #5EEAD4; }
.cell.type-story    { --type-c: #C4B5FD; }
.cell.type-reel     { --type-c: #FDA4AF; }
.cell.has-content:hover {
  background:
    linear-gradient(155deg, rgba(255,255,255,0.42) 0%, rgba(255,255,255,0.22) 55%, rgba(255,255,255,0.12) 100%);
  border-color: rgba(255,255,255,0.7);
  box-shadow:
    0 0 0 1px rgba(255,255,255,0.15),
    0 0 36px rgba(255,255,255,0.1),
    0 16px 40px rgba(0,0,0,0.55),
    inset 0 1px 0 rgba(255,255,255,0.25);
  transform: translateY(-2px);
}
.cell.has-content { cursor: grab; }
.cell.has-content:active { cursor: grabbing; }
.cell.dragging {
  opacity: 0.4;
  transform: scale(0.96);
}
.cell.drop-target {
  border-color: var(--accent-cyan) !important;
  background: rgba(103,232,249,0.20) !important;
  box-shadow: 0 0 0 2px var(--accent-cyan), 0 0 26px rgba(103,232,249,0.5) !important;
  transform: scale(1.03);
}
.cell.drop-target.saturday,
.cell.drop-target.holiday {
  border-color: #FBBF24 !important;
  box-shadow: 0 0 0 2px #FBBF24, 0 0 26px rgba(251,191,36,0.5) !important;
}
.cell.drop-target::after {
  content: '↓ שחרר כאן';
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  font-family: var(--font-he);
  font-size: 13px;
  font-weight: 700;
  color: #0B1220;
  background: var(--accent-cyan);
  padding: 6px 14px;
  border-radius: 999px;
  z-index: 10;
  pointer-events: none;
  white-space: nowrap;
}
.cell.drop-target.saturday::after,
.cell.drop-target.holiday::after {
  content: '⚠ שבת/חג - שחרר אם בכוונה';
  background: #FBBF24;
}

.cell.friday:not(.has-content) {
  background: var(--paper-3);
}
.cell.saturday:not(.has-content) {
  background: rgba(251,191,36,0.03);
  border-color: rgba(251,191,36,0.14);
}
.cell.outside {
  background: transparent !important;
  border-color: var(--border-soft) !important;
}
.cell.outside .cell-head { opacity: 0.35; }
.cell.outside .cell-body { display: none; }
.cell.outside .cell-num,
.cell.outside .cell-heb { color: var(--ink-faint); }

.cell.holiday::before {
  content: '';
  position: absolute;
  top: 0; right: 0;
  width: 0; height: 0;
  border-style: solid;
  border-width: 14px 14px 0 0;
  border-color: var(--gold) transparent transparent transparent;
  opacity: 0.92;
  pointer-events: none;
  z-index: 1;
}

/* Today indicator - distinct from cell type colors. Default = amber-yellow for Zeliger.
   Badge appears AS A FLOATING TAB above the cell (doesn't overlap Hebrew date). */
.cell.is-today {
  border-color: #FACC15 !important;
  box-shadow: 0 0 0 2px #FACC15, 0 0 32px rgba(250,204,21,0.5) !important;
  animation: today-pulse 2.5s ease-in-out infinite;
  overflow: visible !important;
}
@keyframes today-pulse {
  0%, 100% { box-shadow: 0 0 0 2px #FACC15, 0 0 24px rgba(250,204,21,0.4); }
  50% { box-shadow: 0 0 0 2px #FACC15, 0 0 40px rgba(250,204,21,0.7); }
}
.cell.is-today .cell-num {
  color: #FACC15;
  font-weight: 700;
}
.cell.is-today::after {
  content: 'היום';
  position: absolute;
  top: -10px;
  left: 50%;
  transform: translateX(-50%);
  background: #FACC15;
  color: #0B1220;
  font-family: var(--font-he);
  font-size: 10px;
  font-weight: 800;
  padding: 2px 12px;
  border-radius: 999px;
  letter-spacing: 0.05em;
  z-index: 3;
  box-shadow: 0 2px 8px rgba(250,204,21,0.45);
  white-space: nowrap;
}

/* CELL HEAD: numbers, dates */
.cell-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 6px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(148,163,184,0.1);
  min-height: 28px;
}
.cell-num {
  font-family: var(--font-en);
  font-size: 17px;
  font-weight: 600;
  color: var(--ink);
  line-height: 1;
  letter-spacing: -0.02em;
}
.cell-heb {
  font-family: var(--font-he);
  font-size: 11px;
  color: var(--ink-soft);
  font-weight: 500;
  line-height: 1.3;
}
.cell-hol {
  width: 100%;
  font-family: var(--font-he);
  font-size: 10px;
  font-weight: 600;
  color: var(--gold);
  margin-top: 2px;
  letter-spacing: 0.01em;
}

.cell-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex: 1;
  padding-top: 4px;
}

.cell-type-row {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
  width: 100%;
}
.cell-type-chip {
  font-family: var(--font-he);
  font-size: 10px;
  font-weight: 700;
  color: #0B1220;
  background: var(--type-c);
  border: none;
  padding: 3px 12px;
  border-radius: 999px;
  letter-spacing: 0.03em;
  box-shadow: 0 2px 8px color-mix(in srgb, var(--type-c) 35%, transparent);
}
.cell-warning {
  font-size: 11px;
  color: #FBBF24;
  cursor: help;
}
.cell-title {
  font-family: var(--font-he);
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.35;
  text-align: center;
  padding: 6px 4px 4px;
  overflow: hidden;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Bottom action zone - FULL-WIDTH tray that hits the cell's outer edges exactly */
.cell-footer {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-top: auto;
  margin-left: -10px;
  margin-right: -10px;
  margin-bottom: -9px;
  padding: 10px 12px;
  background: rgba(255,255,255,0.14);
  border-top: 1px solid rgba(255,255,255,0.24);
  width: calc(100% + 20px);
}
.cell-status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  width: 100%;
}
.cell-status-label {
  font-family: var(--font-he);
  font-size: 11px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: 0.02em;
  text-transform: none;
}
.cell-status {
  font-family: var(--font-he);
  font-size: 10px;
  font-weight: 600;
  padding: 3px 18px 3px 9px;
  border-radius: 999px;
  cursor: pointer;
  appearance: none;
  border: 1px solid transparent;
  letter-spacing: 0.01em;
  background-image: linear-gradient(45deg, transparent 50%, currentColor 50%), linear-gradient(135deg, currentColor 50%, transparent 50%);
  background-position: calc(100% - 10px) 50%, calc(100% - 6px) 50%;
  background-size: 4px 4px;
  background-repeat: no-repeat;
  background-color: transparent;
  transition: all 0.15s ease;
}
.cell-status:focus { outline: none; }
.cell-status option { background: var(--paper); color: var(--ink); }

.cell-open {
  font-family: var(--font-he);
  font-size: 11px;
  font-weight: 700;
  color: #0B1220;
  background: #FFFFFF;
  border: 1px solid #FFFFFF;
  padding: 5px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
  letter-spacing: 0.01em;
  width: 100%;
  text-align: center;
}
.cell-open:hover {
  background: var(--type-c, #67E8F9);
  border-color: var(--type-c, #67E8F9);
  color: #0B1220;
}

/* (item-card legacy CSS removed - cell IS the card now) */

/* MODAL */
.modal-bg {
  position: fixed;
  inset: 0;
  background: rgba(7, 16, 31, 0.78);
  backdrop-filter: blur(8px);
  display: none;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 40px 20px;
}
.modal-bg.open { display: flex; }
.modal {
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: 18px;
  max-width: 1100px;
  width: 100%;
  max-height: 92vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
  direction: rtl;
}
.modal-head {
  padding: 26px 32px 22px;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  background: var(--paper);
  z-index: 2;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 18px;
}
.modal-head-left .modal-pill {
  font-family: var(--font-he);
  font-size: 11px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 999px;
  display: inline-block;
  margin-bottom: 12px;
}
.modal-head-left h2 {
  margin: 0;
  font-family: var(--font-he);
  font-size: 26px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.015em;
}
.modal-head-left .date-row {
  margin-top: 10px;
  font-family: var(--font);
  font-size: 12.5px;
  color: var(--ink-soft);
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.modal-head-left .date-row .dot {
  width: 4px; height: 4px; border-radius: 50%; background: var(--ink-mute);
}
.modal-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.status-select {
  font-family: var(--font-he);
  font-size: 12px;
  font-weight: 500;
  background: var(--paper-2);
  border: 1px solid var(--border);
  color: var(--ink);
  padding: 4px 28px 4px 10px;
  border-radius: 999px;
  cursor: pointer;
  appearance: none;
  background-image: linear-gradient(45deg, transparent 50%, var(--ink-soft) 50%), linear-gradient(135deg, var(--ink-soft) 50%, transparent 50%);
  background-position: calc(100% - 14px) 50%, calc(100% - 9px) 50%;
  background-size: 5px 5px;
  background-repeat: no-repeat;
}
.status-dot {
  width: 9px; height: 9px; border-radius: 50%;
  box-shadow: 0 0 6px currentColor;
}

.modal-close {
  background: rgba(148,163,184,0.08);
  border: 1px solid var(--border);
  font-size: 18px;
  font-weight: 500;
  color: var(--ink-soft);
  width: 36px; height: 36px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
  flex-shrink: 0;
}
.modal-close:hover {
  background: rgba(148,163,184,0.18);
  color: var(--ink);
}

.modal-body { padding: 22px 32px 32px; }

/* ONE-LINE explanation + source row */
.modal-explainline {
  font-family: var(--font-he);
  font-size: 15px;
  line-height: 1.55;
  color: var(--ink);
  margin-bottom: 8px;
  padding: 14px 18px;
  background: rgba(103,232,249,0.06);
  border-right: 3px solid rgba(103,232,249,0.6);
  border-radius: 8px;
}
.modal-source {
  font-family: var(--font-he);
  font-size: 12.5px;
  color: var(--ink-soft);
  margin-bottom: 22px;
  padding: 0 4px;
  direction: rtl;
  text-align: right;
}
.modal-source-label {
  color: var(--ink-mute);
  font-weight: 600;
  margin-left: 4px;
}

.status-text {
  font-family: var(--font-he);
  font-size: 12px;
  font-weight: 600;
  color: var(--ink);
}

/* PRIMARY ROW: image dropzone (left) + accompanying copy (right) */
.modal-primary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
  margin-bottom: 28px;
}
@media (max-width: 820px) { .modal-primary { grid-template-columns: 1fr; } }

.dropzone {
  background: var(--paper-2);
  border: 2px dashed var(--border);
  border-radius: 14px;
  min-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
  position: relative;
  overflow: hidden;
}
.dropzone:hover {
  border-color: var(--accent-cyan);
  background: rgba(103,232,249,0.04);
}
.dropzone.has-image { padding: 0; border-style: solid; }
.dropzone img.uploaded {
  max-width: 100%;
  max-height: 380px;
  border-radius: 12px;
  display: block;
}
.dropzone .dz-icon {
  width: 44px; height: 44px;
  color: var(--ink-mute);
}
.dropzone .dz-text {
  font-family: var(--font-he);
  font-size: 14px;
  color: var(--ink-soft);
  text-align: center;
  font-weight: 500;
}
.dropzone .dz-sub {
  font-family: var(--font);
  font-size: 11.5px;
  color: var(--ink-mute);
}
.dropzone input[type="file"] { display: none; }
.dz-remove {
  position: absolute;
  top: 10px; left: 10px;
  background: rgba(0,0,0,0.55);
  border: 1px solid rgba(255,255,255,0.15);
  color: white;
  border-radius: 999px;
  font-size: 11px;
  padding: 4px 12px;
  cursor: pointer;
  display: none;
}
.dropzone.has-image .dz-remove { display: block; }

.copy-area {
  display: flex;
  flex-direction: column;
}
.copy-area label {
  font-family: var(--font-he);
  font-size: 11px;
  font-weight: 600;
  color: var(--ink-mute);
  letter-spacing: 0.04em;
  margin-bottom: 8px;
}
.copy-area textarea {
  font-family: var(--font-he);
  font-size: 14px;
  line-height: 1.65;
  color: var(--ink);
  background: var(--paper-2);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 18px 18px;
  resize: none;
  flex: 1;
  min-height: 280px;
  direction: rtl;
  text-align: right;
  transition: border-color 0.15s ease;
}
.copy-area textarea:focus {
  outline: none;
  border-color: var(--accent-cyan);
}
.copy-area textarea::placeholder { color: var(--ink-faint); }
.copy-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 10px;
}
.copy-save-btn {
  font-family: var(--font-he);
  font-size: 12.5px;
  font-weight: 700;
  color: #0B1220;
  background: var(--accent-cyan);
  border: 1px solid var(--accent-cyan);
  padding: 7px 18px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
  letter-spacing: 0.01em;
}
.copy-save-btn:hover {
  background: #38BDF8;
  border-color: #38BDF8;
}
.copy-save-btn.is-dirty {
  background: #FBBF24;
  border-color: #FBBF24;
  color: #0B1220;
}
.copy-save-btn.saved-flash {
  background: #22C55E;
  border-color: #22C55E;
  color: #0B1220;
}
.copy-saved {
  font-family: var(--font-he);
  font-size: 11.5px;
  color: var(--ink-mute);
  text-align: left;
  min-height: 14px;
}

/* View-mode read-only copy area */
.copy-view {
  font-family: var(--font-he);
  font-size: 14px;
  line-height: 1.7;
  color: var(--ink);
  background: var(--paper-2);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 18px;
  min-height: 280px;
  white-space: pre-wrap;
  direction: rtl;
  text-align: right;
}
.dz-empty {
  color: var(--ink-mute);
  font-style: italic;
}

/* SECONDARY: original explanation + 2x3 options collapsible */
.modal-section {
  margin-bottom: 22px;
}
.modal-section:last-child { margin-bottom: 0; }
.modal-section > h3 {
  margin: 0 0 12px;
  font-family: var(--font-he);
  font-size: 11px;
  font-weight: 700;
  color: var(--ink-mute);
  letter-spacing: 0.08em;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-soft);
}
.explanation {
  font-family: var(--font-he);
  font-size: 14px;
  line-height: 1.7;
  color: var(--ink-soft);
  white-space: pre-wrap;
}

details.collapsible {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--paper-2);
  margin-bottom: 12px;
}
details.collapsible > summary {
  font-family: var(--font-he);
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  padding: 14px 18px;
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
details.collapsible > summary::-webkit-details-marker { display: none; }
details.collapsible > summary::after {
  content: '+';
  font-family: var(--font-en);
  font-size: 18px;
  font-weight: 300;
  color: var(--ink-soft);
  transition: transform 0.15s ease;
}
details.collapsible[open] > summary::after { content: '−'; }
details.collapsible > .pair {
  padding: 0 18px 18px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
@media (max-width: 700px) { details.collapsible > .pair { grid-template-columns: 1fr; } }
.pair-item {
  background: var(--paper);
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  padding: 14px 16px;
}
.pair-item .pair-label {
  font-family: var(--font-he);
  font-size: 11px;
  font-weight: 600;
  color: var(--ink-mute);
  margin-bottom: 8px;
  letter-spacing: 0.04em;
}
.pair-item .pair-text {
  font-family: var(--font-he);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  color: var(--ink);
}

.footer {
  margin-top: 28px;
  text-align: center;
  font-family: var(--font-en);
  font-size: 11px;
  color: var(--ink-mute);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.footer-brand {
  color: var(--ink-soft);
  font-weight: 600;
  margin-inline-start: 6px;
}
.footer-link {
  color: var(--accent-cyan);
  text-decoration: none;
  font-weight: 700;
  transition: color 0.15s ease;
}
.footer-link:hover {
  color: #FACC15;
  text-decoration: underline;
}
body.theme-uria .footer-link {
  color: #22D3EE;
}
body.theme-uria .footer-link:hover {
  color: #FF6B35;
}
'''


JS = '''
const ITEMS_DATA = __ITEMS_JSON__;
const itemsByNum = Object.fromEntries(ITEMS_DATA.map(i => [i.num, i]));
const CLIENT_KEY = '__CLIENT_KEY__';

const STATUS_COLORS = {
  'בעבודה': '#3B82F6',
  'בעיצוב': '#F97316',
  'ממתין לאישור': '#EAB308',
  'אושר': '#22C55E',
};
const STATUS_ORDER = ['בעבודה', 'בעיצוב', 'ממתין לאישור', 'אושר'];

/* ---------- localStorage helpers (per-client, per-item) ---------- */
function lsKey(num, field) { return `gantt:${CLIENT_KEY}:${num}:${field}`; }
function getLocal(num, field, fallback) {
  try { return localStorage.getItem(lsKey(num, field)) ?? fallback; } catch (e) { return fallback; }
}
function setLocal(num, field, value) {
  try { localStorage.setItem(lsKey(num, field), value); } catch (e) {}
}

/* ---------- View mode (URL ?mode=view) ---------- */
function isViewMode() {
  return new URLSearchParams(window.location.search).get('mode') === 'view';
}
if (isViewMode()) document.body.classList.add('view-mode');

/* Download as PDF - uses browser print dialog with print-friendly CSS */
window.downloadPDF = function() {
  window.print();
};

/* Share with client = copy ?mode=view link */
window.shareView = function(btn) {
  const url = new URL(window.location.href);
  url.searchParams.set('mode', 'view');
  url.hash = '';
  navigator.clipboard.writeText(url.toString()).then(() => {
    const orig = btn.querySelector('span').textContent;
    btn.querySelector('span').textContent = '✓ הקישור הועתק';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.querySelector('span').textContent = orig;
      btn.classList.remove('copied');
    }, 2000);
  }).catch(() => {
    prompt('העתק את הקישור הבא ושלח ללקוח:', url.toString());
  });
};

/* ---------- Status decoration on cells (read from localStorage) ---------- */
function paintStatus(selectEl) {
  const status = selectEl.value;
  const c = STATUS_COLORS[status] || STATUS_COLORS['בעבודה'];
  selectEl.style.color = c;
  selectEl.style.borderColor = c;
  selectEl.style.borderWidth = '2px';
  selectEl.style.borderStyle = 'solid';
  selectEl.style.fontWeight = '700';
  selectEl.style.background = `color-mix(in srgb, ${c} 12%, transparent)`;
}

function applyStatusToCells() {
  document.querySelectorAll('.cell-status').forEach(sel => {
    const num = parseInt(sel.dataset.num);
    const status = getLocal(num, 'status', itemsByNum[num]?.status || 'בעבודה');
    sel.value = status;
    paintStatus(sel);
  });
}

/* Wire cell-status changes */
document.addEventListener('change', (e) => {
  if (e.target.classList.contains('cell-status')) {
    const sel = e.target;
    const num = parseInt(sel.dataset.num);
    setLocal(num, 'status', sel.value);
    paintStatus(sel);
  }
});

/* ---------- Today highlight ---------- */
function highlightToday() {
  const now = new Date();
  const iso = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
  document.querySelectorAll(`.cell[data-iso="${iso}"]`).forEach(c => c.classList.add('is-today'));
}

/* ---------- Drag & Drop ---------- */
let dragSourceCell = null;

function isViewModeStrict() { return document.body.classList.contains('view-mode'); }

function setupDragAndDrop() {
  if (isViewModeStrict()) return;  // No drag in view mode

  document.addEventListener('dragstart', (e) => {
    const cell = e.target.closest('.cell.has-content');
    if (!cell) return;
    dragSourceCell = cell;
    cell.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    const item = cell.querySelector('[data-num]');
    if (item) {
      e.dataTransfer.setData('application/json', JSON.stringify({
        num: parseInt(item.dataset.num),
        iso: cell.dataset.iso
      }));
    }
  });

  document.addEventListener('dragend', () => {
    document.querySelectorAll('.dragging').forEach(c => c.classList.remove('dragging'));
    document.querySelectorAll('.drop-target').forEach(c => c.classList.remove('drop-target'));
    dragSourceCell = null;
  });

  document.addEventListener('dragover', (e) => {
    const cell = e.target.closest('.cell:not(.outside)');
    if (!cell || cell === dragSourceCell) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    document.querySelectorAll('.drop-target').forEach(c => {
      if (c !== cell) c.classList.remove('drop-target');
    });
    cell.classList.add('drop-target');
  });

  document.addEventListener('drop', (e) => {
    e.preventDefault();
    const target = e.target.closest('.cell:not(.outside)');
    if (!target || target === dragSourceCell) {
      document.querySelectorAll('.drop-target').forEach(c => c.classList.remove('drop-target'));
      return;
    }

    let data;
    try { data = JSON.parse(e.dataTransfer.getData('application/json')); }
    catch (err) { return; }

    const srcNum = data.num;
    const tgtIso = target.dataset.iso;

    // Warn if dropping on Shabbat or holiday
    if (target.classList.contains('saturday') || target.classList.contains('holiday')) {
      const where = target.classList.contains('holiday') ? 'חג' : 'שבת';
      if (!confirm(`היעד הוא ${where}. בטוח שלהעביר תוכן ליום הזה?`)) {
        target.classList.remove('drop-target');
        return;
      }
    }

    // Check if target has content - swap dates
    const tgtItem = target.querySelector('[data-num]');
    setLocal(srcNum, 'date_override', tgtIso);
    if (tgtItem) {
      const tgtNum = parseInt(tgtItem.dataset.num);
      setLocal(tgtNum, 'date_override', data.iso);
    }

    // Reload to re-apply all overrides cleanly
    location.reload();
  });
}

/* ---------- Apply date overrides on page load ---------- */
function applyDateOverrides() {
  let movedAny = false;
  // Build map: desiredIso → array of item nums
  const moves = [];
  ITEMS_DATA.forEach(item => {
    const override = getLocal(item.num, 'date_override', null);
    if (override && override !== item.date) {
      moves.push({ num: item.num, fromIso: item.date, toIso: override });
    }
  });

  // Show restore button if any overrides
  if (moves.length > 0) {
    document.getElementById('restoreBtn')?.classList.add('visible');
    movedAny = true;
  }

  // Apply moves - extract content from origin cells, swap or place in target
  moves.forEach(({ num, fromIso, toIso }) => {
    const sourceItem = document.querySelector(`.cell[data-iso="${fromIso}"] [data-num="${num}"]`);
    if (!sourceItem) return;
    const sourceCell = sourceItem.closest('.cell');
    const targetCell = document.querySelector(`.cell[data-iso="${toIso}"]:not(.outside)`);
    if (!sourceCell || !targetCell || sourceCell === targetCell) return;

    // Move entire body content
    const sourceBody = sourceCell.querySelector('.cell-body');
    const targetBody = targetCell.querySelector('.cell-body');
    if (!sourceBody || !targetBody) return;

    // Capture content + type class
    const sourceContent = sourceBody.innerHTML;
    const sourceTypeClass = Array.from(sourceCell.classList).find(c => c.startsWith('type-'));
    const targetContent = targetBody.innerHTML;
    const targetTypeClass = Array.from(targetCell.classList).find(c => c.startsWith('type-'));

    // Move source content to target (swap if both had content)
    targetBody.innerHTML = sourceContent;
    sourceBody.innerHTML = targetContent;

    // Clear ALL type classes from both cells before re-adding
    ['type-post', 'type-carousel', 'type-story', 'type-reel'].forEach(c => {
      sourceCell.classList.remove(c);
      targetCell.classList.remove(c);
    });

    // Target now holds source's content - apply source's type
    targetCell.classList.add('has-content');
    if (sourceTypeClass) targetCell.classList.add(sourceTypeClass);
    targetCell.setAttribute('draggable', 'true');

    if (targetContent.trim()) {
      // Source now holds target's old content - apply target's type
      sourceCell.classList.add('has-content');
      if (targetTypeClass) sourceCell.classList.add(targetTypeClass);
      sourceCell.setAttribute('draggable', 'true');
    } else {
      // Source is now empty
      sourceCell.classList.remove('has-content');
      sourceCell.setAttribute('draggable', 'false');
    }
  });

  if (movedAny) applyStatusToCells();  // Reapply status after DOM shuffle
}

window.restoreOriginal = function() {
  if (!confirm('להחזיר את כל התכנים למיקומם המקורי?')) return;
  ITEMS_DATA.forEach(item => {
    try { localStorage.removeItem(lsKey(item.num, 'date_override')); } catch (e) {}
  });
  location.reload();
};

/* ---------- Month picker (dropdown) ---------- */
const monthSelect = document.querySelector('.month-select');
if (monthSelect) {
  monthSelect.addEventListener('change', () => {
    const m = monthSelect.value;
    document.querySelectorAll('.month').forEach(s => s.classList.toggle('active', s.dataset.month === m));
    try { localStorage.setItem('gantt:active-month:' + CLIENT_KEY, m); } catch (e) {}
  });
  try {
    const saved = localStorage.getItem('gantt:active-month:' + CLIENT_KEY);
    if (saved && [...monthSelect.options].some(o => o.value === saved)) {
      monthSelect.value = saved;
      document.querySelectorAll('.month').forEach(s => s.classList.toggle('active', s.dataset.month === saved));
    }
  } catch (e) {}
}

/* ---------- Modal ---------- */
function openModal(num) {
  const it = itemsByNum[num];
  if (!it) return;

  const status = getLocal(num, 'status', it.status || 'בעבודה');
  const savedCopy = getLocal(num, 'copy', '');
  const savedImg = getLocal(num, 'img', '');

  const statusOpts = STATUS_ORDER.map(s =>
    `<option value="${s}" ${s === status ? 'selected' : ''}>${s}</option>`
  ).join('');

  const modal = document.getElementById('modal');
  const inner = document.getElementById('modal-inner');

  const isView = isViewMode();
  inner.innerHTML = `
    <div class="modal-head">
      <div class="modal-head-left">
        <span class="modal-pill" style="background:${it.type_soft}; color:${it.type_accent}; border:1px solid ${it.type_accent}40;">${it.type_label}</span>
        <h2>${escapeHtml(it.title)}</h2>
        <div class="date-row">
          <span>${formatDateHe(it.date)} (יום ${escapeHtml(it.day)})</span>
          <span class="dot"></span>
          <span class="modal-status">
            <span class="status-dot" id="statusDot" style="background:${STATUS_COLORS[status]}; box-shadow:0 0 8px ${STATUS_COLORS[status]};"></span>
            ${isView
              ? `<span class="status-text">${escapeHtml(status)}</span>`
              : `<select class="status-select" id="statusSelect" data-num="${num}">${statusOpts}</select>`
            }
          </span>
        </div>
      </div>
      <button class="modal-close" aria-label="סגור" onclick="closeModal()">×</button>
    </div>
    <div class="modal-body">
      ${it.short_explanation ? `<div class="modal-explainline">${escapeHtml(it.short_explanation)}</div>` : ''}
      ${it.source ? `<div class="modal-source"><span class="modal-source-label">מקור:</span> ${escapeHtml(it.source)}</div>` : ''}

      <div class="modal-primary">
        <div class="copy-area">
          <label>קופי נלווה ${isView ? '' : '(ניתן לעריכה)'}</label>
          ${isView
            ? `<div class="copy-view">${escapeHtml(savedCopy || '— טרם נכתב קופי —')}</div>`
            : `<textarea id="copyArea" data-num="${num}" placeholder="כתוב כאן את הקופי הסופי לפרסום...">${escapeHtml(savedCopy)}</textarea>
               <div class="copy-actions">
                 <button class="copy-save-btn" id="copySaveBtn">שמור קופי</button>
                 <span class="copy-saved" id="copySaved"></span>
               </div>`
          }
        </div>
        <div class="dropzone ${savedImg ? 'has-image' : ''} ${isView ? 'view-mode' : ''}" id="dropzone" data-num="${num}">
          ${!isView ? `<input type="file" id="fileInput" accept="image/*">` : ''}
          ${savedImg
            ? `<img class="uploaded" src="${savedImg}" alt="ויזואל" />${!isView ? `<button class="dz-remove" onclick="event.stopPropagation(); removeImage(${num})">הסר</button>` : ''}`
            : (isView
                ? `<div class="dz-text dz-empty">— אין עדיין תמונה —</div>`
                : `<svg class="dz-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
                   <div class="dz-text">גרור תמונה לכאן או לחץ לבחירה</div>
                   <div class="dz-sub">PNG · JPG · WebP</div>`)
          }
        </div>
      </div>
    </div>
  `;

  modal.classList.add('open');
  document.body.style.overflow = 'hidden';

  // View mode = no interactivity, exit early
  if (isViewMode()) return;

  // Wire up status select
  const sel = document.getElementById('statusSelect');
  const dot = document.getElementById('statusDot');
  if (sel) {
    sel.addEventListener('change', () => {
      const v = sel.value;
      setLocal(num, 'status', v);
      const c = STATUS_COLORS[v] || '#94A3B8';
      dot.style.background = c;
      dot.style.boxShadow = `0 0 8px ${c}`;
      applyStatusToCells();
    });
  }

  // Wire up copy editor with explicit SAVE button (no more silent autosave)
  const ta = document.getElementById('copyArea');
  const saveBtn = document.getElementById('copySaveBtn');
  const savedHint = document.getElementById('copySaved');
  if (ta && saveBtn) {
    let dirty = false;
    ta.addEventListener('input', () => {
      dirty = true;
      saveBtn.classList.add('is-dirty');
      saveBtn.textContent = 'שמור קופי *';
      savedHint.textContent = '';
    });
    saveBtn.addEventListener('click', () => {
      setLocal(num, 'copy', ta.value);
      dirty = false;
      saveBtn.classList.remove('is-dirty');
      saveBtn.classList.add('saved-flash');
      saveBtn.textContent = '✓ נשמר';
      savedHint.textContent = '';
      setTimeout(() => {
        saveBtn.classList.remove('saved-flash');
        saveBtn.textContent = 'שמור קופי';
      }, 1800);
    });
    // Ctrl/Cmd+S to save
    ta.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        saveBtn.click();
      }
    });
  }

  // Wire up dropzone
  setupDropzone(num);
}

function setupDropzone(num) {
  const dz = document.getElementById('dropzone');
  const fi = document.getElementById('fileInput');
  if (!dz || !fi) return;
  dz.addEventListener('click', (e) => {
    if (e.target.classList.contains('dz-remove')) return;
    fi.click();
  });
  fi.addEventListener('change', (e) => {
    const f = e.target.files[0];
    if (f) handleImage(num, f);
  });
  dz.addEventListener('dragover', (e) => { e.preventDefault(); dz.style.borderColor = '#67E8F9'; });
  dz.addEventListener('dragleave', () => { dz.style.borderColor = ''; });
  dz.addEventListener('drop', (e) => {
    e.preventDefault();
    dz.style.borderColor = '';
    const f = e.dataTransfer.files[0];
    if (f && f.type.startsWith('image/')) handleImage(num, f);
  });
}

function handleImage(num, file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    const dataUrl = e.target.result;
    setLocal(num, 'img', dataUrl);
    openModal(num);
  };
  reader.readAsDataURL(file);
}

function removeImage(num) {
  try { localStorage.removeItem(lsKey(num, 'img')); } catch (e) {}
  openModal(num);
}

function closeModal() {
  document.getElementById('modal').classList.remove('open');
  document.body.style.overflow = '';
}

function escapeHtml(s) {
  if (!s) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatDateHe(iso) {
  const [y, m, d] = iso.split('-');
  return `${parseInt(d)}.${parseInt(m)}.${y.slice(2)}`;
}

document.addEventListener('click', (e) => {
  // Don't open modal if user clicked the inline status select
  if (e.target.closest('.cell-status')) return;
  // Explicit open button
  const openBtn = e.target.closest('.cell-open');
  if (openBtn) {
    e.stopPropagation();
    const num = parseInt(openBtn.dataset.num);
    if (num) openModal(num);
    return;
  }
  // Clicking anywhere else on a content cell opens modal
  const cell = e.target.closest('.cell.has-content');
  if (cell) {
    const firstItem = cell.querySelector('[data-num]');
    if (firstItem) {
      const num = parseInt(firstItem.dataset.num);
      if (num) openModal(num);
    }
    return;
  }
  if (e.target.classList.contains('modal-bg')) closeModal();
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeModal();
});

highlightToday();
applyDateOverrides();
applyStatusToCells();
setupDragAndDrop();
'''


def render_html(data: dict, logo_b64: str, mode: str = 'zeliger') -> str:
    items = data['items']
    items_by_date = {}
    for it in items:
        items_by_date.setdefault(it['date_iso'], []).append(it)

    client = data['client']
    period = data['period']
    count = data['count']

    dates = sorted(it['date_iso'] for it in items)
    first = dates[0]
    last = dates[-1]
    year_a, month_a = int(first[:4]), int(first[5:7])
    year_b, month_b = int(last[:4]), int(last[5:7])

    # Collect ordered list of months
    months = []
    cur_y, cur_m = year_a, month_a
    while (cur_y, cur_m) <= (year_b, month_b):
        months.append((cur_y, cur_m))
        cur_m += 1
        if cur_m > 12:
            cur_m = 1
            cur_y += 1

    months_html_parts = []
    for i, (y, m) in enumerate(months):
        month_html = render_month(y, m, items_by_date, is_active=(i == 0))
        month_html = render_status_opts_for_items(month_html, items)
        months_html_parts.append(month_html)

    tabs_html = render_tabs(months)
    legend_html = render_legend()
    items_json = render_modal_data(items)

    # Client key for localStorage scoping (slug-ish)
    client_key = ''.join(c if c.isalnum() else '_' for c in client) or 'client'

    js_filled = JS.replace('__ITEMS_JSON__', items_json).replace('__CLIENT_KEY__', client_key)

    if mode == 'uria':
        # Logo 03 - "אוריה ברמן." with tangerine period (per brand kit final-3.html line 988-993)
        logo_tag = (
            '<a class="brand-link" href="https://uriaberman.com" target="_blank" rel="noopener">'
            '<div class="uria-x-logo">'
            '<span class="logo-name-block">'
            'אוריה ברמן'
            '<span class="logo-period">.</span>'
            '</span>'
            '<span class="logo-tagline">Strategy · Creative · Digital · <span class="tag-accent">AI</span></span>'
            '</div>'
            '</a>'
        )
        # English brand name + × separator (brand-kit signature)
        footer_text = (
            '<span class="footer-built">Built by</span>'
            '<span class="footer-x">×</span>'
            '<span class="footer-brand">Uria Berman</span>'
            '<span class="footer-period">.</span>'
        )
    else:
        logo_tag = (
            f'<a class="brand-link" href="https://zeligershomron.co.il" target="_blank" rel="noopener" title="זליגר שומרון">'
            f'<img class="logo" src="data:image/png;base64,{logo_b64}" alt="Zeliger Shomron" />'
            f'</a>'
        )
        footer_text = (
            'Built by <span class="footer-brand">Social · '
            '<a class="footer-link" href="https://zeligershomron.co.il" target="_blank" rel="noopener">Zeliger Shomron</a>'
            '</span>'
        )

    css_with_theme = CSS.replace('__THEME_ROOT__', render_theme_root(mode))
    if mode == 'uria':
        css_with_theme += URIA_OVERRIDES

    # Font links: load both Inter (Zeliger) and Plus Jakarta Sans (Uria)
    font_links = ('<link href="https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Heebo:wght@400;500;700&display=swap" rel="stylesheet">')

    body_class = f'theme-{mode}'

    return f'''<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5" />
<title>{html.escape(client)} | גאנט {html.escape(period)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
{font_links}
<style>{css_with_theme}</style>
</head>
<body class="{body_class}">
<div class="page">
  <header class="header">
    <div class="header-brand">
      {logo_tag}
    </div>
    <div class="header-titles">
      <div class="period-mini">{html.escape(period)}{f' <span class="heb">{data.get("_heb_month","")} {data.get("_heb_year","")}</span>' if data.get('_heb_month') else ''}</div>
      <h1><span class="h1-label">גאנט חודשי</span><span class="h1-sep">{('<span class="x-box-mini">×</span>' if mode == 'uria' else '·')}</span><span class="h1-client">{html.escape(client)}</span></h1>
      <span class="header-hint">גרור קוביה כדי להזיז · לחץ לעריכה</span>
    </div>
  </header>

  <div class="controls">
    {legend_html}
    <div class="control-cluster">
      <button class="share-btn" id="shareBtn" onclick="shareView(this)" title="העתק קישור לתצוגת לקוח (ללא עריכה)">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/></svg>
        <span>שתף עם לקוח</span>
      </button>
      <button class="pdf-btn" id="pdfBtn" onclick="downloadPDF()" title="הורד גאנט כ-PDF">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        <span>הורד PDF</span>
      </button>
      <button class="restore-btn" id="restoreBtn" onclick="restoreOriginal()" title="החזר את כל התכנים למיקומם המקורי">
        <span>↺ החזר למקור</span>
      </button>
      {tabs_html}
    </div>
  </div>

  <div class="months-container">
    {''.join(months_html_parts)}
  </div>

  <div class="footer" dir="ltr">{footer_text}</div>
</div>

<div class="modal-bg" id="modal">
  <div class="modal" id="modal-inner"></div>
</div>

<script>{js_filled}</script>
</body>
</html>
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--logo', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--mode', choices=['zeliger', 'uria'], default='zeliger',
                    help='Brand mode: zeliger (default, dark) or uria (light, brand kit)')
    args = ap.parse_args()

    data = json.loads(Path(args.data).read_text(encoding='utf-8'))
    logo_b64 = base64.b64encode(Path(args.logo).read_bytes()).decode('ascii')

    # Compute Israeli holidays for the period of the data
    dates = sorted([it['date_iso'] for it in data['items'] if it.get('date_iso')])
    if dates:
        from israeli_holidays import get_israeli_holidays, hebrew_month_for_gregorian, hebrew_year_for_gregorian
        # Expand range by 7 days each side to catch nearby holidays
        from datetime import date, timedelta
        first = date.fromisoformat(dates[0])
        last = date.fromisoformat(dates[-1])
        start_ext = (first - timedelta(days=7)).isoformat()
        end_ext = (last + timedelta(days=7)).isoformat()
        holidays = get_israeli_holidays(start_ext, end_ext)
        # Populate the module-level dict that render_cell uses
        HOLIDAYS_2026.update(holidays)
        # Compute Hebrew month for the title
        heb_month = hebrew_month_for_gregorian(first.year, first.month)
        heb_year = hebrew_year_for_gregorian(first.year, first.month)
        data['_heb_month'] = heb_month
        data['_heb_year'] = heb_year

    out_html = render_html(data, logo_b64, mode=args.mode)
    Path(args.out).write_text(out_html, encoding='utf-8')
    print(f'WROTE {args.out} ({len(out_html):,} chars)')
    print(f'  Mode: {args.mode}')
    if HOLIDAYS_2026:
        print(f'  Israeli holidays detected in period: {len(HOLIDAYS_2026)}')


if __name__ == '__main__':
    main()
