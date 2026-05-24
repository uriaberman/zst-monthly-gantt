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
import sys, io, json, html, argparse, base64, calendar, urllib.parse
from datetime import date
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pyluach.dates import GregorianDate


# 4 content types - cool family (cyan/teal/lavender/rose) — original Zeliger palette restored
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
    'נגנז':          '#6B7280',  # slate (archived — visible but disabled)
}

STATUS_ORDER = ['בעבודה', 'בעיצוב', 'ממתין לאישור', 'אושר', 'נגנז']

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

    # Multi-item support: each item inside a cell is its OWN draggable card.
    # Drag operates on the .cell-item level, not the .cell level, so one day can hold
    # multiple posts and the user can move just one of them.
    body_parts = []
    item_can_drag = (not cell['is_outside'])
    type_classes_for_cell = []
    for it in cell['items']:
        tc = TYPE_COLORS.get(it['type_key'], TYPE_COLORS['post'])
        title = html.escape(it['title'])
        type_label = html.escape(tc['label'])
        type_key = html.escape(it['type_key'])
        type_classes_for_cell.append(f'type-{type_key}')
        warning = ''
        if cell.get('is_saturday') or cell.get('holiday'):
            warning = '<span class="cell-warning" title="תוכן זה ממוקם בשבת/חג - שקול להעביר לערב חג / יום שישי">⚠</span>'
        # Bake the is-archived class at server-render time so we don't get a flash of un-dimmed content
        # before JS runs. The JS later toggles it if the user changes status via dropdown.
        archived_cls = ' is-archived' if it.get('status') == 'נגנז' else ''
        drag_attr = 'draggable="true"' if (item_can_drag and not archived_cls) else ''
        body_parts.append(f'''
        <div class="cell-item type-{type_key}{archived_cls}" data-num="{it['num']}" data-iso="{cell['iso']}" {drag_attr}>
          <div class="cell-type-row">
            <span class="cell-type-chip">{type_label}</span>
            {warning}
          </div>
          <div class="cell-title">{title}</div>
          <div class="cell-footer">
            <div class="cell-status-pill" data-num="{it['num']}">
              <span class="cell-status-dot"></span>
              <select class="cell-status" data-num="{it['num']}" aria-label="סטטוס" onclick="event.stopPropagation()">
                __STATUS_OPTS_{it['num']}__
              </select>
            </div>
            <button class="cell-open" data-num="{it['num']}">צפייה ←</button>
          </div>
        </div>''')

    # Keep the cell.type-X classes too (CSS uses them for the glow + chip color)
    if type_classes_for_cell:
        classes.extend(type_classes_for_cell)
    multi_cls = ' multi-item' if len(cell['items']) > 1 else ''
    return f'''<div class="{' '.join(classes)}{multi_cls}" data-iso="{cell['iso']}">
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


def hebrew_date_string(iso: str) -> str:
    """Return Hebrew date with gematria, e.g. 'ז' בסיוון תשפ"ו'."""
    try:
        y, m, d = [int(x) for x in iso.split('-')]
        from pyluach.dates import GregorianDate
        hd = GregorianDate(y, m, d).to_heb()
        return hd.hebrew_date_string()
    except Exception:
        return ''


def render_modal_data(items: list) -> str:
    slim = []
    for it in items:
        tc = TYPE_COLORS.get(it['type_key'], TYPE_COLORS['post'])
        slim.append({
            'num': it['num'],
            'date': it['date_iso'],
            'day': it['day'],
            'heb_date': hebrew_date_string(it['date_iso']),
            'type_key': it['type_key'],
            'type_label': tc['label'],
            'type_accent': tc['accent'],
            'type_soft': tc['soft'],
            'title': it['title'],
            'short_explanation': it.get('short_explanation', ''),
            'source': it.get('source', ''),
            'status': it['status'],
            'media_files': it.get('media_files', []),
            # Visual copy per slide — the TEXT that appears ON each visual.
            'slides': it.get('slides', []),
            # The accompanying caption (קופי נלווה) — the social-post text.
            # CRITICAL: threaded through so the modal's textarea pre-populates from data.json
            # when there's no localStorage draft. Otherwise the modal shows empty and the
            # copy that was extracted from the brief disappears (24.5.26 regression).
            'copy_final': it.get('copy_final', ''),
        })
    return json.dumps(slim, ensure_ascii=False)


THEME_TOKENS = {
    'zeliger': {
        # Original Zeliger navy-dark palette (restored at user request — keep prior design language)
        'bg': '#07101F', 'paper': '#0F1A2E', 'paper-2': '#14223A',
        'paper-3': '#0C1828', 'paper-4': '#18253F',
        'ink': '#F1F5F9', 'ink-soft': '#94A3B8', 'ink-faint': '#475569', 'ink-mute': '#64748B',
        'border': '#1E2D45', 'border-soft': '#182338',
        'accent-primary': '#67E8F9', 'accent-secondary': '#A78BFA', 'accent-warm': '#FB7185',
        'gold': '#FACC15',
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
/* Uria today: thick TANGERINE ring + strong tangerine glow ring — same color as the "היום" badge.
   Win over .cell.type-post / .cell.type-carousel / etc with explicit !important + outline:none. */
body.theme-uria .cell.is-today,
body.theme-uria .cell.is-today.type-post,
body.theme-uria .cell.is-today.type-carousel,
body.theme-uria .cell.is-today.type-story,
body.theme-uria .cell.is-today.type-reel {
  border: 3px solid #FF6B35 !important;
  outline: none !important;
  box-shadow:
    0 0 0 4px rgba(255,107,53,0.28),
    0 0 0 1px #FF6B35 inset,
    0 0 32px rgba(255,107,53,0.60),
    0 0 64px rgba(255,107,53,0.30) !important;
  animation: uria-today-glow 2.4s ease-in-out infinite;
}
@keyframes uria-today-glow {
  0%, 100% {
    box-shadow:
      0 0 0 4px rgba(255,107,53,0.22),
      0 0 0 1px #FF6B35 inset,
      0 0 28px rgba(255,107,53,0.55),
      0 0 56px rgba(255,107,53,0.28);
  }
  50% {
    box-shadow:
      0 0 0 5px rgba(255,107,53,0.30),
      0 0 0 1px #FF6B35 inset,
      0 0 36px rgba(255,107,53,0.70),
      0 0 72px rgba(255,107,53,0.40);
  }
}
body.theme-uria .cell.is-today .cell-num { color: #FF6B35 !important; }
body.theme-uria .cell.is-today::after {
  background: #FF6B35;
  color: #FFFFFF;
  box-shadow: 0 2px 8px rgba(255,107,53,0.45);
  font-family: 'Rubik', sans-serif;  /* Hebrew text - must be Rubik */
}
/* (uria-today-pulse replaced by uria-today-glow defined later — keep this anchor for diff history) */
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
/* Uria buttons - IDENTICAL pair: both filled brand tangerine.
   Share + PDF look exactly the same. Single visual language. */
body.theme-uria .share-btn,
body.theme-uria .pdf-btn {
  color: #FAFAFA !important;
  background: #FF6B35 !important;
  border: 1px solid #FF6B35 !important;
  font-family: 'Rubik', sans-serif !important;
  font-weight: 700 !important;
  letter-spacing: 0 !important;
  padding: 7px 16px !important;
}
body.theme-uria .share-btn:hover,
body.theme-uria .pdf-btn:hover {
  background: #FF8A65 !important;
  border-color: #FF8A65 !important;
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
  align-items: center;          /* Vertically center with text */
  justify-content: center;
  width: auto !important;
  height: 1em !important;        /* Match h1 line-box so × sits on baseline like a hyphen */
  background: transparent !important;
  box-shadow: none !important;
  margin: 0 10px !important;
}
body.theme-uria .h1-sep .x-box-mini {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: #FF6B35;             /* Brand tangerine × acting as a static separator */
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-weight: 700;
  font-size: 32px;             /* Big + static, centered on the line */
  line-height: 1;
  letter-spacing: 0;
  /* NO transform / NO rotate animation — user requested static */
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
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: #FF6B35;
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-weight: 700;
  font-size: 22px;
  line-height: 1;
  margin: 0 4px;
  height: 1em;             /* Snap to baseline like a separator */
  vertical-align: middle;
}
body.theme-uria .footer-brand {
  font-family: 'Plus Jakarta Sans', sans-serif;
  color: #FAFAFA;
  font-weight: 900;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-size: 14px;
  text-decoration: none;
}
body.theme-uria .footer-link-wa {
  display: inline-flex;
  align-items: baseline;
  gap: 0;
  color: #FAFAFA;
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: color 0.15s ease, border-color 0.15s ease;
  cursor: pointer;
}
body.theme-uria .footer-link-wa:hover {
  color: #FF6B35;
  border-bottom-color: #FF6B35;
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

/* Restored Zeliger header: glass panel with cyan accent strip */
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
  font-weight: 500;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--accent-cyan);
  opacity: 0.95;
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
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  font-family: var(--font-he);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--ink-soft);
  margin-bottom: 2px;
}
.period-mini .period-greg {
  font-family: var(--font-he);
  color: var(--accent-cyan);
  font-weight: 700;
  font-size: 13px;
  letter-spacing: 0.02em;
}
.period-mini .period-dot {
  color: var(--ink-faint);
  font-weight: 400;
  opacity: 0.6;
}
.period-mini .period-heb {
  font-family: var(--font-he);
  color: var(--ink-soft);
  font-weight: 500;
  font-size: 12px;
  letter-spacing: 0.02em;
}
body.theme-uria .period-mini .period-greg { color: #C4B5FD; }
body.theme-uria .period-mini .period-heb { color: #FF8A65; }
body.theme-uria .period-mini .period-dot { color: rgba(255,255,255,0.35); }
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
.share-btn,
.pdf-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-he);
  font-size: 12px;
  font-weight: 700;
  color: #FACC15;                         /* Restored yellow (previous version) */
  background: rgba(250,204,21,0.10);
  border: 1px solid rgba(250,204,21,0.40);
  padding: 6px 14px;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.share-btn:hover,
.pdf-btn:hover {
  background: rgba(250,204,21,0.20);
  border-color: #FACC15;
}
.share-btn.copied {
  background: rgba(34,197,94,0.18);
  border-color: #22C55E;
  color: #22C55E;
}
.share-btn.disabled,
.share-btn[disabled] {
  opacity: 0.45;
  cursor: not-allowed;
  background: rgba(148,163,184,0.08);
  border-color: rgba(148,163,184,0.30);
  color: var(--ink-mute);
}
.share-btn.disabled:hover { background: rgba(148,163,184,0.08); border-color: rgba(148,163,184,0.30); }
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
/* .pdf-btn merged into .share-btn rule above */
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
/* Uniform CYAN glow on all content cells (original design — type differentiation via chip only). */
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
/* Type accent via the chip only — original family */
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
/* Iron rule visual: hovering past date during drag = blocked */
.cell.drop-blocked {
  border-color: rgba(239,68,68,0.55) !important;
  background: rgba(239,68,68,0.10) !important;
  cursor: not-allowed !important;
  position: relative;
}
.cell.drop-blocked::after {
  content: 'תאריך עבר ✕';
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  background: #DC2626;
  color: #FFFFFF;
  padding: 4px 10px;
  border-radius: 999px;
  font-family: var(--font-he);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  pointer-events: none;
  z-index: 20;
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
  align-items: stretch;
  gap: 6px;
  flex: 1;
  padding-top: 4px;
}

/* INDIVIDUAL ITEM CARD — each post/story/etc inside a cell is its own draggable card.
   Lets the user move ONE item without affecting the others on the same day. */
.cell-item {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px 2px;
  border-radius: 8px;
  cursor: grab;
  transition: all 0.15s ease;
}
.cell-item:active { cursor: grabbing; }
.cell-item.dragging { opacity: 0.4; transform: scale(0.96); }
.cell.multi-item .cell-item:not(:last-child) {
  border-bottom: 1px dashed rgba(255,255,255,0.18);
  padding-bottom: 8px;
  margin-bottom: 2px;
}
.cell.multi-item .cell-item:hover {
  background: rgba(255,255,255,0.05);
}
.cell.multi-item .cell-item .cell-footer {
  margin-left: -8px;
  margin-right: -8px;
  margin-bottom: -2px;
}
body.view-mode .cell-item { cursor: pointer; }
body.view-mode .cell-item.dragging { opacity: 1; transform: none; }

/* ARCHIVED state (status === "נגנז")
   Both Editor and Viewer show archived items dimmed with a small "נגנז" badge.
   The status pill (with its slate color) already says "נגנז" — this just makes
   the WHOLE card visually muted so the eye glides over it without losing it. */
.cell-item.is-archived {
  opacity: 0.45;
  filter: grayscale(0.55);
  cursor: not-allowed !important;
  position: relative;
}
.cell-item.is-archived:hover { opacity: 0.65; }

/* The "נגנז" badge lives on the CELL (not the item) so it sits in the cell-head's
   empty middle area — clearly detached from the type-chip, above the separator.
   Modern browsers (Chrome 105+ / Firefox 121+ / Safari 15.4+) support :has(). */
.cell:has(.cell-item.is-archived)::before {
  content: 'נגנז';
  position: absolute;
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  background: #6B7280;
  color: #FFFFFF;
  font-family: var(--font-he);
  font-size: 10px;
  font-weight: 800;
  padding: 2px 12px;
  border-radius: 999px;
  letter-spacing: 0.06em;
  pointer-events: none;
  box-shadow: 0 1px 3px rgba(0,0,0,0.35);
  z-index: 4;
  white-space: nowrap;
}
/* In view mode the card itself stays clickable for the modal but doesn't pretend to be interactive */
body.view-mode .cell-item.is-archived { cursor: default !important; }
body.theme-uria .cell.multi-item .cell-item:not(:last-child) {
  border-bottom-color: rgba(255,107,53,0.20);
}

.cell-type-row {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
  width: 100%;
}
/* Original solid type chip — dark text on bright color */
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
/* STATUS PILL — single integrated chip: glowing dot + colored text + colored border.
   The dot is INSIDE the pill, sitting next to the status word ("בעבודה" / "אושר" / etc).
   Border = current status color. Background = same color @ 12% tint. */
.cell-status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px 3px 8px;
  border-radius: 999px;
  border: 2px solid var(--status-c, #94A3B8);
  background: color-mix(in srgb, var(--status-c, #94A3B8) 12%, transparent);
  transition: all 0.15s ease;
}
.cell-status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--status-c, #94A3B8);
  box-shadow: 0 0 8px var(--status-c, #94A3B8);
  flex-shrink: 0;
}
.cell-status {
  font-family: var(--font-he);
  font-size: 11px;
  font-weight: 700;
  padding: 0 12px 0 0;
  border: none;
  cursor: pointer;
  appearance: none;
  color: var(--status-c, #94A3B8);
  letter-spacing: 0.01em;
  background-image: linear-gradient(45deg, transparent 50%, currentColor 50%), linear-gradient(135deg, currentColor 50%, transparent 50%);
  background-position: calc(100% - 4px) 50%, calc(100% - 0px) 50%;
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
/* Modal date block: יום א' · 25.5.26 · ז' סיוון תשפ"ו */
.modal-publish-label {
  font-family: var(--font-he);
  font-size: 11px;
  font-weight: 700;
  color: var(--ink-mute);
  letter-spacing: 0.06em;
}
.modal-date-block {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  font-family: var(--font-he);
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
}
.modal-weekday { color: var(--ink); }
.modal-greg {
  font-family: var(--font-en);
  font-weight: 600;
  color: var(--ink-soft);
}
.modal-heb {
  color: var(--accent-cyan);
  font-weight: 600;
  font-size: 12px;
}
/* DATE PICKER — small calendar button inside the date block; clicking opens a native picker */
.modal-date-edit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  margin-inline-start: 4px;
  padding: 0;
  background: rgba(103,232,249,0.10);
  border: 1px solid rgba(103,232,249,0.35);
  border-radius: 6px;
  color: var(--accent-cyan);
  cursor: pointer;
  transition: all 0.15s ease;
  vertical-align: middle;
}
.modal-date-edit:hover {
  background: rgba(103,232,249,0.22);
  border-color: var(--accent-cyan);
  transform: scale(1.05);
}
.modal-date-edit svg { display: block; }
/* The actual <input type="date"> is hidden but functional — clicking the button calls showPicker() on it */
.modal-date-input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
  /* visible enough for the native picker to anchor to it but invisible to the user */
}
body.theme-uria .modal-date-edit {
  background: rgba(255,107,53,0.10);
  border-color: rgba(255,107,53,0.40);
  color: #FF6B35;
}
body.theme-uria .modal-date-edit:hover {
  background: rgba(255,107,53,0.22);
  border-color: #FF6B35;
}
/* Separator before status — hyphen in Zeliger, × in Uria.
   Centered with the adjacent pills (date-block + status-pill ≈ 28px tall). */
.modal-sep {
  display: inline-flex;
  align-self: center;
  align-items: center;
  justify-content: center;
  color: var(--ink-faint);
  font-family: var(--font-en);
  font-size: 20px;
  font-weight: 400;
  line-height: 1;
  height: 28px;
  width: 22px;
  text-align: center;
  vertical-align: middle;
}
.modal-sep-x {
  color: #FF6B35;
  font-weight: 700;
  font-size: 28px;
  line-height: 1;
  /* Same height/align as .modal-sep — stays centered with date + status pills */
}
/* Modal status pill: SAME pattern as the cell pill (colored border, dot inside, colored text) */
.modal-status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px 4px 10px;
  border-radius: 999px;
  border: 2px solid var(--status-c, #94A3B8);
  background: color-mix(in srgb, var(--status-c, #94A3B8) 12%, transparent);
}
.modal-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--status-c, #94A3B8);
  box-shadow: 0 0 8px var(--status-c, #94A3B8);
  flex-shrink: 0;
}
.modal-status-pill .status-text {
  font-family: var(--font-he);
  font-size: 12px;
  font-weight: 700;
  color: var(--status-c, #94A3B8);
  letter-spacing: 0.01em;
}
.modal-status-pill .status-select {
  font-family: var(--font-he);
  font-size: 12px;
  font-weight: 700;
  background: transparent;
  border: none;
  color: var(--status-c, #94A3B8);
  padding: 0 14px 0 0;
  cursor: pointer;
  appearance: none;
  background-image: linear-gradient(45deg, transparent 50%, currentColor 50%), linear-gradient(135deg, currentColor 50%, transparent 50%);
  background-position: calc(100% - 4px) 50%, calc(100% - 0px) 50%;
  background-size: 4px 4px;
  background-repeat: no-repeat;
}
.modal-status-pill .status-select:focus { outline: none; }
.modal-status-pill .status-select option { background: var(--paper); color: var(--ink); }

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

/* MEDIA ZONE: multi-slot gallery with per-type aspect ratio (1:1 or 9:16) + lightbox */
.media-zone {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.media-zone-label {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  font-family: var(--font-he);
  font-size: 12px;
  font-weight: 700;
  color: var(--ink-soft);
}
.media-zone-label-text { color: var(--ink); }
.media-zone-spec {
  font-family: var(--font-en);
  font-size: 11px;
  font-weight: 600;
  color: var(--accent-cyan);
  letter-spacing: 0.04em;
}
body.theme-uria .media-zone-spec { color: #FF6B35; }
/* MEDIA GRID — 5 columns per row, supports up to MAX_MEDIA_SLOTS (10) cards */
.media-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(5, 1fr);
  align-content: start;
}
@media (max-width: 720px) {
  .media-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 480px) {
  .media-grid { grid-template-columns: repeat(2, 1fr); }
}
/* Each card = slot + slide-copy + actions bar BELOW */
.media-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
/* SLIDE COPY — the text that should appear ON each visual.
   For posts: usually 3 lines (ראשית / משנית / בקטן).
   For carousel slides: usually 1 line ("כי אומרים על התורה...").
   This is DISTINCT from the caption (קופי נלווה) which lives in its own textarea. */
.slide-copy {
  background: var(--paper-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  font-family: var(--font-he);
  font-size: 12px;
  line-height: 1.45;
  text-align: right;
}
.slide-copy-title {
  font-family: var(--font-he);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: var(--accent-cyan);
  margin-bottom: 4px;
}
.slide-copy-label {
  font-family: var(--font-en);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ink-mute);
  margin-bottom: 4px;
}
.slide-copy-primary {
  font-family: var(--font-he);
  font-size: 13px;
  font-weight: 800;
  color: var(--ink);
  margin-bottom: 2px;
}
.slide-copy-secondary {
  font-family: var(--font-he);
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-soft);
  margin-bottom: 2px;
}
.slide-copy-small {
  font-family: var(--font-he);
  font-size: 11px;
  font-weight: 500;
  color: var(--ink-mute);
}
.slide-copy-line {
  font-family: var(--font-he);
  font-size: 12px;
  font-weight: 600;
  color: var(--ink);
}
body.theme-uria .slide-copy-title { color: #FF6B35; }
body.theme-uria .slide-copy { background: rgba(255,255,255,0.03); }
.media-slot {
  position: relative;
  border: 2px dashed var(--border);
  border-radius: 10px;
  background: var(--paper-2);
  overflow: hidden;
  cursor: pointer;
  transition: all 0.15s ease;
  width: 100%;
}
.media-slot.ratio-1-1 { aspect-ratio: 1 / 1; }
.media-slot.ratio-9-16 { aspect-ratio: 9 / 16; }
/* Action bar BELOW each image card */
.media-actions {
  display: flex;
  gap: 6px;
}
.media-act {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-family: var(--font-he);
  font-size: 10px;
  font-weight: 700;
  padding: 5px 6px;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid var(--border);
  background: var(--paper-2);
  color: var(--ink-soft);
  transition: all 0.15s ease;
}
.media-act svg { width: 12px; height: 12px; }
.media-act-replace:hover {
  background: rgba(103,232,249,0.12);
  border-color: var(--accent-cyan);
  color: var(--accent-cyan);
}
.media-act-trash:hover {
  background: rgba(239,68,68,0.12);
  border-color: #EF4444;
  color: #EF4444;
}
.media-replace-input { display: none; }
body.theme-uria .media-act { background: rgba(255,255,255,0.03); border-color: #2D1759; color: #C4B5FD; }
body.theme-uria .media-act-replace:hover { background: rgba(34,211,238,0.14); border-color: #22D3EE; color: #22D3EE; }
body.theme-uria .media-act-trash:hover { background: rgba(255,107,53,0.14); border-color: #FF6B35; color: #FF6B35; }
.media-slot.has-image { border-style: solid; border-color: var(--accent-cyan); }
.media-slot .media-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  cursor: zoom-in;
}
/* media-remove button removed — replaced by .media-actions bar below the card */
.media-slot-num {
  position: absolute;
  bottom: 6px; right: 6px;
  background: rgba(0,0,0,0.55);
  border: 1px solid rgba(255,255,255,0.20);
  color: #FFFFFF;
  font-family: var(--font-en);
  font-size: 10px;
  font-weight: 700;
  border-radius: 4px;
  padding: 1px 6px;
}
.media-slot-add {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  text-align: center;
  padding: 12px 10px;
}
.media-slot-add:hover {
  border-color: var(--accent-cyan);
  background: rgba(103,232,249,0.06);
}
.media-slot-add.drag-over {
  border-color: var(--accent-cyan);
  background: rgba(103,232,249,0.14);
  border-style: solid;
}
.media-slot-add .media-file-input { display: none; }
.media-slot-add .media-add-icon {
  width: 28px; height: 28px;
  color: var(--ink-mute);
}
.media-slot-add .media-add-text {
  font-family: var(--font-he);
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-soft);
}
.media-slot-add .media-add-sub {
  font-family: var(--font-en);
  font-size: 10px;
  color: var(--ink-mute);
  letter-spacing: 0.06em;
}
.media-slot-empty {
  display: flex;
  align-items: center;
  justify-content: center;
}
.media-empty-text {
  font-family: var(--font-he);
  font-size: 12px;
  color: var(--ink-mute);
}
/* Uria overrides for media slots */
body.theme-uria .media-slot { background: rgba(255,255,255,0.02); border-color: #2D1759; }
body.theme-uria .media-slot.has-image { border-color: #FF6B35; }
body.theme-uria .media-slot-add:hover { border-color: #FF6B35; background: rgba(255,107,53,0.06); }
body.theme-uria .media-slot-add.drag-over { border-color: #FF6B35; background: rgba(255,107,53,0.14); }
body.theme-uria .media-slot-add .media-add-icon { color: #C4B5FD; }
body.theme-uria .media-slot-add .media-add-text { color: #C4B5FD; }
body.theme-uria .media-slot-add .media-add-sub { color: #8B7BA5; }

/* LIGHTBOX (click image → fullscreen view) */
.lightbox {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.92);
  backdrop-filter: blur(8px);
  /* ───────────────────────── Z-INDEX HIERARCHY (iron rule 13) ─────────────────────────
     0-99    : page chrome (header, cells, controls)
     100-999 : in-page overlays (draft-bar, tooltips, dropdowns)
     1000    : .modal-bg (item view modal)
     2000+   : .lightbox (zoomed image — must open ON TOP of the modal)
     Any new overlay MUST pick a layer above what it visually sits over. Never reuse a band. */
  z-index: 2000;
  align-items: center;
  justify-content: center;
}
.lightbox.open { display: flex; }
.lightbox-img {
  max-width: 92vw;
  max-height: 88vh;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 30px 80px rgba(0,0,0,0.6);
}
.lightbox-close,
.lightbox-prev,
.lightbox-next {
  position: absolute;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.15);
  color: #FFFFFF;
  border-radius: 50%;
  width: 48px; height: 48px;
  font-size: 28px;
  font-weight: 300;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}
.lightbox-close:hover,
.lightbox-prev:hover,
.lightbox-next:hover {
  background: rgba(255,255,255,0.18);
}
.lightbox-close { top: 24px; left: 24px; }
.lightbox-prev { left: 24px; top: 50%; transform: translateY(-50%); }
.lightbox-next { right: 24px; top: 50%; transform: translateY(-50%); }
.lightbox-counter {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.15);
  color: #FFFFFF;
  padding: 6px 14px;
  border-radius: 999px;
  font-family: var(--font-en);
  font-size: 12px;
  font-weight: 700;
}

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

/* PREVIEW TOGGLE — fixed floating button (Editor only) for switching to client-view preview */
.preview-toggle {
  position: fixed;
  bottom: 22px;
  left: 22px;
  z-index: 900;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--paper);
  color: var(--ink);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 10px 18px;
  font-family: var(--font-he);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 6px 18px rgba(0,0,0,0.45), 0 0 0 1px rgba(255,255,255,0.04) inset;
  transition: all 0.2s ease;
}
.preview-toggle:hover {
  background: var(--paper-2);
  border-color: var(--accent-cyan);
  color: var(--accent-cyan);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(103,232,249,0.18);
}
.preview-toggle.is-preview-mode {
  background: var(--accent-cyan);
  color: var(--bg);
  border-color: var(--accent-cyan);
}
.preview-toggle.is-preview-mode:hover {
  background: var(--ink);
  color: var(--bg);
}
.preview-toggle-icon { flex-shrink: 0; }
.preview-banner {
  position: fixed;
  top: 22px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 900;
  background: rgba(103,232,249,0.15);
  border: 1px solid var(--accent-cyan);
  color: var(--accent-cyan);
  font-family: var(--font-he);
  font-size: 13px;
  font-weight: 700;
  padding: 10px 22px;
  border-radius: 999px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.4);
  backdrop-filter: blur(6px);
}
.preview-banner[hidden] { display: none; }
/* Uria themed variants */
body.theme-uria .preview-toggle {
  background: #160730;
  border-color: rgba(255,107,53,0.40);
  color: #FAFAFA;
}
body.theme-uria .preview-toggle:hover {
  border-color: #FF6B35;
  color: #FF6B35;
  box-shadow: 0 8px 24px rgba(255,107,53,0.22);
}
body.theme-uria .preview-toggle.is-preview-mode {
  background: #FF6B35;
  color: #0A0418;
  border-color: #FF6B35;
}
body.theme-uria .preview-banner {
  background: rgba(255,107,53,0.15);
  border-color: #FF6B35;
  color: #FF8A65;
}

/* DRAFT BAR — appears when there are unpublished local changes */
.draft-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: rgba(250,204,21,0.10);
  border: 1px solid rgba(250,204,21,0.45);
  border-radius: 10px;
  padding: 10px 16px;
  margin-bottom: 14px;
  font-family: var(--font-he);
  font-size: 13px;
  font-weight: 600;
  color: #FACC15;
}
.draft-bar[hidden] { display: none !important; }
.draft-bar-actions { display: inline-flex; gap: 8px; }
.draft-bar-publish {
  background: #FACC15;
  color: #0B1220;
  border: none;
  border-radius: 8px;
  padding: 6px 16px;
  font-family: var(--font-he);
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}
.draft-bar-publish:hover { background: #EAB308; }
.draft-bar-discard {
  background: transparent;
  color: #FACC15;
  border: 1px solid rgba(250,204,21,0.45);
  border-radius: 8px;
  padding: 6px 12px;
  font-family: var(--font-he);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.draft-bar-discard:hover { background: rgba(250,204,21,0.10); }
.draft-bar.publish-busy {
  background: rgba(103,232,249,0.10); border-color: rgba(103,232,249,0.45); color: var(--accent-cyan);
}
.draft-bar.publish-busy .draft-bar-publish {
  background: var(--accent-cyan); color: var(--bg); cursor: progress; opacity: 0.7;
}
.draft-bar.publish-success {
  background: rgba(52,211,153,0.10); border-color: rgba(52,211,153,0.45); color: #34D399;
}
.draft-bar.publish-success .draft-bar-publish {
  background: #34D399; color: var(--bg);
}
.draft-bar.publish-error {
  background: rgba(239,68,68,0.10); border-color: rgba(239,68,68,0.45); color: #EF4444;
}
.draft-bar.publish-error .draft-bar-publish {
  background: #EF4444; color: #FFFFFF;
}
body.theme-uria .draft-bar { background: rgba(255,107,53,0.10); border-color: rgba(255,107,53,0.45); color: #FF8A65; }
body.theme-uria .draft-bar-publish { background: #FF6B35; color: #FAFAFA; }
body.theme-uria .draft-bar-publish:hover { background: #FF8A65; }
body.theme-uria .draft-bar-discard { color: #FF8A65; border-color: rgba(255,107,53,0.45); }
body.theme-uria .draft-bar-discard:hover { background: rgba(255,107,53,0.10); }

/* FOOTER META: last updated + view-mode badge */
.footer-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 24px;
  padding: 10px 4px;
  font-family: var(--font-he);
  font-size: 11px;
  color: var(--ink-mute);
  border-top: 1px solid var(--border);
}
.footer-meta .last-updated {
  font-family: var(--font-he);
  font-weight: 500;
}
.footer-meta .last-updated #lastUpdatedTime {
  font-family: var(--font-en);
  color: var(--ink-soft);
  font-weight: 600;
  margin-inline-start: 4px;
}
.footer-meta .view-mode-badge {
  font-family: var(--font-he);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(103,232,249,0.08);
  border: 1px solid rgba(103,232,249,0.30);
  color: var(--accent-cyan);
}
body.view-mode .footer-meta .view-mode-badge {
  background: rgba(167,139,250,0.08);
  border-color: rgba(167,139,250,0.30);
  color: #A78BFA;
}
body.theme-uria .footer-meta .view-mode-badge {
  background: rgba(34,211,238,0.08);
  border-color: rgba(34,211,238,0.30);
  color: #22D3EE;
}
body.theme-uria.view-mode .footer-meta .view-mode-badge {
  background: rgba(255,107,53,0.08);
  border-color: rgba(255,107,53,0.40);
  color: #FF6B35;
}

.footer {
  margin-top: 12px;
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
const MONTHS_META = __MONTHS_META_JSON__;
const VIEW_MODE_BAKED = __VIEW_MODE_BAKED__;   // true = this HTML is the frozen Viewer
const VIEWER_URL = '__VIEWER_URL__';
const LAST_UPDATED = '__LAST_UPDATED__';

const STATUS_COLORS = {
  'בעבודה': '#3B82F6',
  'בעיצוב': '#F97316',
  'ממתין לאישור': '#EAB308',
  'אושר': '#22C55E',
  'נגנז': '#6B7280',   // archived — same value as Python, see STATUS_COLORS in build.py
};
const STATUS_ORDER = ['בעבודה', 'בעיצוב', 'ממתין לאישור', 'אושר', 'נגנז'];

/* ---------- localStorage helpers (per-client, per-item) ---------- */
function lsKey(num, field) { return `gantt:${CLIENT_KEY}:${num}:${field}`; }
function getLocal(num, field, fallback) {
  try { return localStorage.getItem(lsKey(num, field)) ?? fallback; } catch (e) { return fallback; }
}
function setLocal(num, field, value) {
  try { localStorage.setItem(lsKey(num, field), value); } catch (e) {}
}

/* ---------- View mode (baked into HTML at build time + legacy URL ?mode=view) ---------- */
function isViewMode() {
  if (VIEW_MODE_BAKED) return true;  // The Viewer HTML always returns true
  return new URLSearchParams(window.location.search).get('mode') === 'view';
}
if (isViewMode()) document.body.classList.add('view-mode');

/* Download as PDF - uses browser print dialog with print-friendly CSS */
window.downloadPDF = function() {
  window.print();
};

/* Share with client = copy the dedicated Viewer URL (different file, frozen, read-only).
   Adds ?v=<unix-time> cache-buster so the client always lands on the freshly published HTML
   (without it, GitHub Pages CDN can serve a stale copy for up to ~10 minutes). */
window.shareView = function(btn) {
  let url = VIEWER_URL;
  if (!url) {
    const base = window.location.href.replace(/[/]?(view[/]?)?(\\?.*)?(#.*)?$/, '/');
    url = base + 'view/';
  }
  const sep = url.includes('?') ? '&' : '?';
  url = `${url}${sep}v=${Date.now()}`;
  navigator.clipboard.writeText(url).then(() => {
    const orig = btn.querySelector('span').textContent;
    btn.querySelector('span').textContent = '✓ הקישור הועתק';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.querySelector('span').textContent = orig;
      btn.classList.remove('copied');
    }, 2000);
  }).catch(() => {
    prompt('העתק את הקישור הבא ושלח ללקוח:', url);
  });
};

/* ===========================================================================
   PUBLISH WORKFLOW — one-click via GitHub API
   ===========================================================================
   When user clicks "פרסם שינויים":
     1. Collect draft changes from localStorage
     2. Get GitHub PAT from localStorage (prompt one-time if missing)
     3. Fetch current data.json from GitHub
     4. Merge changes into data.json
     5. Commit via GitHub API (single API call, ~1 second)
     6. GitHub Action auto-rebuilds HTMLs (~60-90 seconds)
     7. Pages redeploys

   The user never leaves the Editor URL. Status indicator shows progress.
   If anything fails: clear error + user can bring the issue to chat. */

const GITHUB_REPO  = 'uriaberman/zst-monthly-gantt';
const GITHUB_BRANCH = 'main';
const PAT_STORAGE_KEY = 'gantt:github-pat';

function getStoredPAT() {
  try { return localStorage.getItem(PAT_STORAGE_KEY) || ''; } catch (e) { return ''; }
}

function setStoredPAT(token) {
  try { localStorage.setItem(PAT_STORAGE_KEY, token); } catch (e) {}
}

function clearStoredPAT() {
  try { localStorage.removeItem(PAT_STORAGE_KEY); } catch (e) {}
}

function promptForPAT() {
  const instructions = (
    'נדרש GitHub Personal Access Token חד-פעמי.\\n\\n' +
    '1. פתח: https://github.com/settings/tokens?type=beta\\n' +
    '2. "Generate new token (fine-grained)"\\n' +
    '3. Repository access: רק zst-monthly-gantt\\n' +
    '4. Permissions: Contents: Read & write\\n' +
    '5. העתק את הטוקן והדבק כאן:'
  );
  const token = prompt(instructions, '');
  if (token && token.trim().length > 10) {
    setStoredPAT(token.trim());
    return token.trim();
  }
  return null;
}

async function ghApiRequest(path, opts = {}) {
  const token = getStoredPAT();
  if (!token) throw new Error('NO_TOKEN');
  const r = await fetch(`https://api.github.com${path}`, {
    ...opts,
    headers: {
      'Accept': 'application/vnd.github+json',
      'Authorization': `Bearer ${token}`,
      'X-GitHub-Api-Version': '2022-11-28',
      ...(opts.headers || {}),
    },
  });
  if (r.status === 401) { clearStoredPAT(); throw new Error('BAD_TOKEN'); }
  if (!r.ok) throw new Error(`GH_API_${r.status}: ${await r.text()}`);
  return r.json();
}

function setPublishStatus(stateText, kind /* 'idle'|'busy'|'success'|'error' */) {
  const bar = document.getElementById('draftBar');
  if (!bar) return;
  const text = bar.querySelector('.draft-bar-text');
  const publishBtn = bar.querySelector('.draft-bar-publish');
  if (text) text.textContent = stateText;
  if (publishBtn) {
    publishBtn.disabled = kind === 'busy';
    if (kind === 'busy')        publishBtn.textContent = '⏳ מפרסם…';
    else if (kind === 'success') publishBtn.textContent = '✅ פורסם';
    else if (kind === 'error')   publishBtn.textContent = '↻ נסה שוב';
    else                         publishBtn.textContent = '📤 פרסם שינויים';
  }
  bar.classList.toggle('publish-busy',    kind === 'busy');
  bar.classList.toggle('publish-success', kind === 'success');
  bar.classList.toggle('publish-error',   kind === 'error');
}

/* Apply browser draft to the data.json structure that GitHub stores */
function mergeChangesIntoData(serverData, drafts) {
  const out = JSON.parse(JSON.stringify(serverData));
  const byNum = {};
  out.items.forEach(it => { byNum[String(it.num)] = it; });
  for (const [numStr, draft] of Object.entries(drafts)) {
    const it = byNum[numStr];
    if (!it) continue;
    if (draft.date)   it.date_iso     = draft.date;
    if (draft.status) it.status       = draft.status;
    if (draft.copy)   it.copy_final   = draft.copy;
  }
  return out;
}

window.requestPublish = async function() {
  const draftChanges = collectDraftChanges();
  if (Object.keys(draftChanges.items).length === 0) {
    alert('אין שינויים בטיוטה לפרסום.');
    return;
  }

  // 1. Ensure we have a PAT
  let token = getStoredPAT();
  if (!token) {
    token = promptForPAT();
    if (!token) {
      alert('פרסום בוטל — אין טוקן.');
      return;
    }
  }

  setPublishStatus('שולח שינויים ל-GitHub…', 'busy');

  try {
    // 2. Identify which data file we're updating (depends on slug & CLIENT_KEY)
    //    For now, derive from the URL: /<slug>/ → pilots/<slug>/data.json
    const pathParts = window.location.pathname.split('/').filter(Boolean);
    // pathParts is like ['zst-monthly-gantt', 'shlichut-horaa'] or similar; the slug is the last segment
    const slug = pathParts[pathParts.length - 1];
    const dataPath = `pilots/${slug}/data.json`;

    // 3. Fetch current data.json from GitHub (need its SHA to update)
    const fileMeta = await ghApiRequest(`/repos/${GITHUB_REPO}/contents/${encodeURIComponent(dataPath)}?ref=${GITHUB_BRANCH}`);
    const currentB64 = fileMeta.content.replace(/\\n/g, '');
    const currentBytes = atob(currentB64);
    const currentText = decodeURIComponent(escape(currentBytes));
    const currentData = JSON.parse(currentText);

    // 4. Apply local drafts
    const newData = mergeChangesIntoData(currentData, draftChanges.items);
    const newText = JSON.stringify(newData, null, 2);
    // Base64-encode the UTF-8 text
    const newB64 = btoa(unescape(encodeURIComponent(newText)));

    // 5. Commit the new data.json
    const summary = Object.entries(draftChanges.items)
      .map(([num, d]) => `#${num}: ${Object.keys(d).join('+')}`)
      .join(', ');
    await ghApiRequest(`/repos/${GITHUB_REPO}/contents/${encodeURIComponent(dataPath)}`, {
      method: 'PUT',
      body: JSON.stringify({
        message: `${slug}: publish draft (${summary})`,
        content: newB64,
        sha: fileMeta.sha,
        branch: GITHUB_BRANCH,
      }),
    });

    // 6. Success on GitHub side — clear local drafts (they're now in the source of truth).
    discardLocalDraftsSilent();
    // 7. Now WAIT for the GitHub Action to rebuild + Pages to serve the new HTML
    //    before we let the user share the link. Otherwise the client sees old content.
    setShareEnabled(false);
    const expectedAfter = LAST_UPDATED;  // The CURRENT published_at; new build will be newer
    pollDeploy(VIEWER_URL || (window.location.pathname + 'view/'), expectedAfter);
    return;

  } catch (err) {
    console.error(err);
    let msg = 'שגיאה בפרסום.';
    if (err.message === 'NO_TOKEN')   msg = 'הפרסום בוטל — לא הוזן טוקן.';
    else if (err.message === 'BAD_TOKEN') msg = 'הטוקן פג / נדחה. נסה שוב.';
    else if (err.message.startsWith('GH_API_')) msg = 'GitHub API החזיר שגיאה: ' + err.message;
    setPublishStatus(msg + ' לעזרה — חזור לצ\\'אט עם Claude.', 'error');
  }
};

/* Lock / unlock the "שיתוף" button. Locked = the link still points to stale content. */
function setShareEnabled(enabled) {
  const btn = document.getElementById('shareBtn');
  if (!btn) return;
  btn.disabled = !enabled;
  btn.classList.toggle('disabled', !enabled);
  const span = btn.querySelector('span');
  if (!enabled) {
    if (span && !span.dataset.origText) span.dataset.origText = span.textContent;
    if (span) span.textContent = '⏳ ממתין לפריסה…';
    btn.title = 'הפריסה עדיין רצה. תוכל לשתף ברגע שהבר ייצבע ירוק.';
  } else {
    if (span && span.dataset.origText) { span.textContent = span.dataset.origText; delete span.dataset.origText; }
    btn.title = 'העתק קישור צפייה ללקוח';
  }
}

/* Poll the Viewer URL until its lastUpdatedTime is newer than what we had pre-publish.
   That's our signal that the GitHub Action finished, Pages redeployed, and the client
   will now see the new content. Only THEN we re-enable Share. */
async function pollDeploy(viewerUrl, expectedAfter) {
  if (!viewerUrl) {
    setPublishStatus('✅ פורסם. רענן ידנית בעוד כדקה.', 'success');
    setShareEnabled(true);
    return;
  }
  const start = Date.now();
  const MAX_WAIT_MS = 5 * 60 * 1000;  // 5 minutes hard ceiling
  setPublishStatus('⏳ פורסם ל-GitHub. ממתין שה-Action ייצור HTML חדש (כדקה)…', 'busy');

  let attempt = 0;
  const tick = async () => {
    attempt++;
    const elapsed = Math.round((Date.now() - start) / 1000);
    try {
      const r = await fetch(viewerUrl + '?nc=' + Date.now(), { cache: 'no-store' });
      const html = await r.text();
      const m = html.match(/id="lastUpdatedTime"[^>]*>([^<]+)</);
      const liveStamp = m ? m[1].trim() : '';
      if (liveStamp && liveStamp !== expectedAfter) {
        setPublishStatus(`✅ העדכון חי בכתובת הלקוח (${elapsed} שניות). אפשר לשתף.`, 'success');
        setShareEnabled(true);
        return;
      }
    } catch (e) { /* network blips: try again */ }

    if (Date.now() - start > MAX_WAIT_MS) {
      setPublishStatus(`⚠ עברו ${elapsed} שניות והעדכון לא נראה ב-Viewer. בדוק את Actions ב-GitHub.`, 'error');
      setShareEnabled(true);  // Don't lock forever
      return;
    }
    setPublishStatus(`⏳ ממתין לפריסה… (${elapsed} שניות) — בדרך כלל לוקח 60-90 שניות.`, 'busy');
    setTimeout(tick, 8000);
  };
  setTimeout(tick, 12000);  // First check after 12s (Action checkout + setup takes that long)
}

/* Clear local drafts without confirmation (called after successful publish) */
function discardLocalDraftsSilent() {
  ITEMS_DATA.forEach(it => {
    try { localStorage.removeItem(lsKey(it.num, 'date_override')); } catch(e){}
    try { localStorage.removeItem(lsKey(it.num, 'status')); } catch(e){}
    try { localStorage.removeItem(lsKey(it.num, 'copy')); } catch(e){}
  });
}

window.discardDraft = function() {
  if (!confirm('לבטל את כל השינויים שטרם פורסמו?')) return;
  ITEMS_DATA.forEach(it => {
    try { localStorage.removeItem(lsKey(it.num, 'date_override')); } catch(e){}
    try { localStorage.removeItem(lsKey(it.num, 'status')); } catch(e){}
    try { localStorage.removeItem(lsKey(it.num, 'copy')); } catch(e){}
  });
  location.reload();
};

/* Collect all unpublished changes from localStorage into a structured payload */
function collectDraftChanges() {
  const items = {};
  ITEMS_DATA.forEach(it => {
    const num = it.num;
    const draft = {};
    const d = getLocal(num, 'date_override', null);
    if (d && d !== it.date) draft.date = d;
    const s = getLocal(num, 'status', null);
    if (s && s !== it.status) draft.status = s;
    const c = getLocal(num, 'copy', null);
    if (c) draft.copy = c;
    if (Object.keys(draft).length > 0) items[num] = draft;
  });
  return { items: items };
}

/* Show the draft bar whenever there are local changes (Editor only) */
function updateDraftBar() {
  if (VIEW_MODE_BAKED) return;  // viewer never shows the bar
  const bar = document.getElementById('draftBar');
  if (!bar) return;
  const ch = collectDraftChanges();
  const count = Object.keys(ch.items).length;
  bar.hidden = count === 0;
  const text = bar.querySelector('.draft-bar-text');
  if (text && count > 0) {
    text.textContent = `⚠ יש לך ${count} שינוי${count > 1 ? 'ים' : ''} בטיוטה — הלקוח עדיין לא רואה אותם`;
  }
}

/* ---------- Status decoration on cells (read from localStorage) ----------
   Paints the wrapper .cell-status-pill via CSS var --status-c. Border + dot + text
   all derive from this single variable, so they stay perfectly in sync. */
function paintStatus(selectEl) {
  const status = selectEl.value;
  const c = STATUS_COLORS[status] || STATUS_COLORS['בעבודה'];
  const pill = selectEl.closest('.cell-status-pill');
  if (pill) pill.style.setProperty('--status-c', c);
  else { selectEl.style.color = c; }
  // 5th status "נגנז" — toggle the is-archived class on the parent cell-item so CSS
  // can dim the whole card (cell-level CSS handles the visual treatment)
  const item = selectEl.closest('.cell-item');
  if (item) item.classList.toggle('is-archived', status === 'נגנז');
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
    updateDraftBar();
  }
});

/* ---------- Today highlight ---------- */
function highlightToday() {
  const now = new Date();
  const iso = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
  document.querySelectorAll(`.cell[data-iso="${iso}"]`).forEach(c => c.classList.add('is-today'));
}

/* ---------- Drag & Drop (item-level) ---------- */
let dragSourceItem = null;
function sourceCellOf(item) { return item ? item.closest('.cell') : null; }

function isViewModeStrict() { return document.body.classList.contains('view-mode'); }

function todayIsoIsrael() {
  // YYYY-MM-DD in Israel timezone (works in browser without date-fns-tz)
  const opts = { timeZone: 'Asia/Jerusalem', year: 'numeric', month: '2-digit', day: '2-digit' };
  const parts = new Intl.DateTimeFormat('en-CA', opts).formatToParts(new Date());
  const y = parts.find(p => p.type === 'year').value;
  const m = parts.find(p => p.type === 'month').value;
  const d = parts.find(p => p.type === 'day').value;
  return `${y}-${m}-${d}`;
}

function isPastIso(iso) {
  // Iron rule: cannot drop on a date that has already passed chronologically
  return iso < todayIsoIsrael();
}

function setupDragAndDrop() {
  if (isViewModeStrict()) return;  // No drag in view mode

  // Drag operates on individual .cell-item elements (NOT the whole cell).
  // This way, if a day has multiple posts, the user can move just one of them.
  document.addEventListener('dragstart', (e) => {
    const item = e.target.closest('.cell-item');
    if (!item) return;
    // Archived items (status === נגנז) can't be moved — must be un-archived first
    if (item.classList.contains('is-archived')) {
      e.preventDefault();
      return;
    }
    dragSourceItem = item;
    item.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('application/json', JSON.stringify({
      num: parseInt(item.dataset.num),
      iso: item.dataset.iso
    }));
  });

  document.addEventListener('dragend', () => {
    document.querySelectorAll('.dragging').forEach(c => c.classList.remove('dragging'));
    document.querySelectorAll('.drop-target, .drop-blocked').forEach(c => { c.classList.remove('drop-target'); c.classList.remove('drop-blocked'); });
    dragSourceItem = null;
  });

  document.addEventListener('dragover', (e) => {
    const cell = e.target.closest('.cell:not(.outside)');
    const srcCell = sourceCellOf(dragSourceItem);
    if (!cell || cell === srcCell) return;
    if (isPastIso(cell.dataset.iso)) {
      cell.classList.add('drop-blocked');
      e.dataTransfer.dropEffect = 'none';
      return;
    }
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    document.querySelectorAll('.drop-target, .drop-blocked').forEach(c => {
      if (c !== cell) { c.classList.remove('drop-target'); c.classList.remove('drop-blocked'); }
    });
    cell.classList.add('drop-target');
  });

  document.addEventListener('drop', (e) => {
    e.preventDefault();
    const target = e.target.closest('.cell:not(.outside)');
    const srcCell = sourceCellOf(dragSourceItem);
    if (!target || target === srcCell) {
      document.querySelectorAll('.drop-target, .drop-blocked').forEach(c => { c.classList.remove('drop-target'); c.classList.remove('drop-blocked'); });
      return;
    }
    // Iron rule: cannot drop on a past date (silent reject - hover already showed it)
    if (isPastIso(target.dataset.iso)) {
      target.classList.remove('drop-target');
      target.classList.remove('drop-blocked');
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

    // ITEM-LEVEL move: just place the source item on the target's date.
    // Target's existing items stay where they are (a day can hold multiple posts).
    // No more "swap" — the user explicitly drags one item; the destination grows.
    setLocal(srcNum, 'date_override', tgtIso);
    location.reload();
  });
}

/* ---------- Apply date overrides on page load (item-level moves) ----------
   New behavior (v9.1+):
     • Each draft moves ONE item, not a whole cell.
     • Destination day grows by 1 if it already had items (multi-item day).
     • Source day shrinks by 1; if now 0 items it becomes empty.
   This is the only correct behavior when a single day can hold multiple posts. */
function applyDateOverrides() {
  const moves = [];
  ITEMS_DATA.forEach(item => {
    const override = getLocal(item.num, 'date_override', null);
    if (override && override !== item.date) {
      moves.push({ num: item.num, fromIso: item.date, toIso: override });
    }
  });
  if (moves.length === 0) return;
  document.getElementById('restoreBtn')?.classList.add('visible');

  moves.forEach(({ num, fromIso, toIso }) => {
    // 1. Find the item element by num (may already have been moved by an earlier override)
    const itemEl = document.querySelector(`.cell-item[data-num="${num}"]`);
    if (!itemEl) return;
    const sourceCell = itemEl.closest('.cell');
    const targetCell = document.querySelector(`.cell[data-iso="${toIso}"]:not(.outside)`);
    if (!sourceCell || !targetCell || sourceCell === targetCell) return;
    const targetBody = targetCell.querySelector('.cell-body');
    if (!targetBody) return;

    // 2. Update the item's own data-iso to its new home
    itemEl.dataset.iso = toIso;

    // 3. Move the item DOM node into the target cell-body
    targetBody.appendChild(itemEl);

    // 4. Recompute classes for SOURCE cell after the move
    refreshCellChrome(sourceCell);
    // 5. Recompute classes for TARGET cell after the move
    refreshCellChrome(targetCell);
  });

  applyStatusToCells();  // Reapply status painting after DOM shuffle
}

/* Recompute .has-content, .multi-item, and .type-X classes on a cell based on its current children */
function refreshCellChrome(cell) {
  if (!cell) return;
  const items = cell.querySelectorAll('.cell-item');
  // Strip all type-X classes
  ['type-post', 'type-carousel', 'type-story', 'type-reel'].forEach(c => cell.classList.remove(c));
  cell.classList.remove('has-content');
  cell.classList.remove('multi-item');
  if (items.length === 0) return;
  cell.classList.add('has-content');
  if (items.length > 1) cell.classList.add('multi-item');
  // Inherit each item's type — cell glow comes from the FIRST item's type
  items.forEach(it => {
    const tc = Array.from(it.classList).find(c => c.startsWith('type-'));
    if (tc) cell.classList.add(tc);
  });
}

window.restoreOriginal = function() {
  if (!confirm('להחזיר את כל התכנים למיקומם המקורי?')) return;
  ITEMS_DATA.forEach(item => {
    try { localStorage.removeItem(lsKey(item.num, 'date_override')); } catch (e) {}
  });
  location.reload();
};

/* ---------- Preview toggle (Editor only) — see exactly what the client sees ----------
   Toggling adds/removes body.view-mode. All existing CSS rules for body.view-mode
   already hide the edit chrome (status dropdowns become static, share button hides,
   draft bar hides, etc.). The modal also reads isViewMode() each time it opens so
   the next click on a cell will render in the preview state. */
window.togglePreviewMode = function() {
  const body = document.body;
  const banner = document.getElementById('previewBanner');
  const btn = document.getElementById('previewToggle');
  if (!btn) return;
  const label = btn.querySelector('.preview-toggle-label');
  const goingToView = !body.classList.contains('view-mode');
  body.classList.toggle('view-mode', goingToView);
  if (banner) banner.hidden = !goingToView;
  if (label) label.textContent = goingToView ? '✏ חזרה לעריכה' : 'צפה כלקוח';
  btn.classList.toggle('is-preview-mode', goingToView);
  // Close any open modal — it will re-render properly next time it opens
  const modal = document.getElementById('modal');
  if (modal && modal.classList.contains('open')) closeModal();
};

/* ---------- Month picker (dropdown) + dynamic period label ---------- */
function updatePeriodLabel(monthKey) {
  const meta = MONTHS_META[monthKey];
  if (!meta) return;
  const gregEl = document.getElementById('periodGreg');
  const hebEl = document.getElementById('periodHeb');
  if (gregEl) gregEl.textContent = meta.greg;
  if (hebEl) hebEl.textContent = meta.heb;
}

const monthSelect = document.querySelector('.month-select');
if (monthSelect) {
  monthSelect.addEventListener('change', () => {
    const m = monthSelect.value;
    document.querySelectorAll('.month').forEach(s => s.classList.toggle('active', s.dataset.month === m));
    updatePeriodLabel(m);
    try { localStorage.setItem('gantt:active-month:' + CLIENT_KEY, m); } catch (e) {}
  });
  try {
    const saved = localStorage.getItem('gantt:active-month:' + CLIENT_KEY);
    if (saved && [...monthSelect.options].some(o => o.value === saved)) {
      monthSelect.value = saved;
      document.querySelectorAll('.month').forEach(s => s.classList.toggle('active', s.dataset.month === saved));
      updatePeriodLabel(saved);
    }
  } catch (e) {}
}

/* ---------- Modal ---------- */
function openModal(num) {
  const it = itemsByNum[num];
  if (!it) return;

  const status = getLocal(num, 'status', it.status || 'בעבודה');
  // PRIORITY: localStorage draft (if user has edited locally) → fall back to copy_final from data.json
  // (the caption extracted from the brief). Otherwise the modal would show empty even though
  // data.json already has the caption — that's the 24.5.26 regression that lost data.
  const localCopy = getLocal(num, 'copy', null);
  const savedCopy = (localCopy !== null && localCopy !== '') ? localCopy : (it.copy_final || '');
  // PRIORITY: file-based media baked into the item at build time (visible to the client).
  // Falls back to localStorage drafts only if no files exist on disk.
  let savedImages;
  if (Array.isArray(it.media_files) && it.media_files.length > 0) {
    savedImages = it.media_files.slice();
  } else {
    const legacyImg = getLocal(num, 'img', '');
    savedImages = getLocal(num, 'images', null);
    if (!Array.isArray(savedImages)) savedImages = legacyImg ? [legacyImg] : [];
  }

  const statusOpts = STATUS_ORDER.map(s =>
    `<option value="${s}" ${s === status ? 'selected' : ''}>${s}</option>`
  ).join('');

  const modal = document.getElementById('modal');
  const inner = document.getElementById('modal-inner');

  const isView = isViewMode();
  const isUriaMode = document.body.classList.contains('theme-uria');
  const sepChar = isUriaMode ? '×' : '–';
  const sepCls = isUriaMode ? 'modal-sep modal-sep-x' : 'modal-sep';
  const statusColor = STATUS_COLORS[status] || '#94A3B8';
  // The item's CURRENT date — respects any local override from drag-drop or earlier picker change
  const currentIso = getLocal(num, 'date_override', null) || it.date;
  // Media aspect ratio per content type: 1:1 for post/carousel, 9:16 for story/reel
  const isVertical = (it.type_key === 'story' || it.type_key === 'reel');
  const ratioCls = isVertical ? 'ratio-9-16' : 'ratio-1-1';
  const aspectLabel = isVertical ? '9:16 · 1080×1920' : '1:1 · 1080×1080';
  inner.innerHTML = `
    <div class="modal-head">
      <div class="modal-head-left">
        <span class="modal-pill" style="background:${it.type_soft}; color:${it.type_accent}; border:1px solid ${it.type_accent}40;">${it.type_label}</span>
        <h2>${escapeHtml(it.title)}</h2>
        <div class="date-row" dir="rtl">
          <span class="modal-publish-label">תאריך פרסום:</span>
          <span class="modal-date-block">
            <span class="modal-weekday">יום ${escapeHtml(it.day)}</span>
            <span class="modal-greg">${formatDateHe(currentIso)}</span>
            ${it.heb_date ? `<span class="modal-heb" id="modalHebDate">${escapeHtml(it.heb_date)}</span>` : ''}
            ${isView ? '' : `
              <button class="modal-date-edit" id="modalDateEdit" title="שנה תאריך ידנית" type="button"
                      aria-label="פתח לוח שנה לשינוי תאריך">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
              </button>
              <input type="date" class="modal-date-input" id="modalDateInput" value="${currentIso}" min="${todayIsoIsrael()}" data-num="${num}" />
            `}
          </span>
          <span class="${sepCls}">${sepChar}</span>
          <span class="modal-status-pill" id="modalStatusPill" style="--status-c:${statusColor};">
            <span class="modal-status-dot"></span>
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
        <div class="media-zone ${ratioCls}" data-num="${num}" data-type="${it.type_key}">
          <div class="media-zone-label">
            <span class="media-zone-label-text">ויזואל</span>
            <span class="media-zone-spec">${aspectLabel}</span>
          </div>
          <div class="media-grid" id="mediaGrid">
            ${renderMediaSlots(num, savedImages, ratioCls, isView, it.slides)}
          </div>
        </div>
      </div>
    </div>
  `;

  modal.classList.add('open');
  document.body.style.overflow = 'hidden';

  // View mode = no interactivity, exit early
  if (isViewMode()) return;

  // Wire up status select — repaint the modal status pill (border + dot + text all from --status-c)
  const sel = document.getElementById('statusSelect');
  const modalPill = document.getElementById('modalStatusPill');
  if (sel) {
    sel.addEventListener('change', () => {
      const v = sel.value;
      setLocal(num, 'status', v);
      const c = STATUS_COLORS[v] || '#94A3B8';
      if (modalPill) modalPill.style.setProperty('--status-c', c);
      applyStatusToCells();
      updateDraftBar();
    });
  }

  // Wire up the date picker: button reveals the hidden <input type="date">, picking a date
  // sets a date_override (same channel that drag-drop uses) and reloads to re-apply.
  const dateBtn = document.getElementById('modalDateEdit');
  const dateInput = document.getElementById('modalDateInput');
  if (dateBtn && dateInput) {
    dateBtn.addEventListener('click', (e) => {
      e.preventDefault();
      // Use the native showPicker() where supported, fall back to focus
      if (typeof dateInput.showPicker === 'function') {
        try { dateInput.showPicker(); } catch (err) { dateInput.focus(); dateInput.click(); }
      } else {
        dateInput.focus();
        dateInput.click();
      }
    });
    dateInput.addEventListener('change', () => {
      const newIso = dateInput.value;
      if (!newIso) return;
      if (isPastIso(newIso)) {
        alert('אסור לקבוע תאריך עבר. בחר תאריך מהיום והלאה.');
        dateInput.value = currentIso;
        return;
      }
      if (newIso === currentIso) return;  // no-op
      setLocal(num, 'date_override', newIso);
      // Reload so applyDateOverrides moves the item visually + draft bar reflects the change
      location.reload();
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
      updateDraftBar();
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

  // Wire up media drag/drop on the add-slot
  setupMediaDrop(num);
}

/* ---------- Media slots (multi-image gallery, per-type aspect ratio) ----------
   PRIORITY: file-based media (committed in repo, visible to client) over localStorage (preview only).
   If the item has `media_files` baked in at build time → use those paths.
   Otherwise → fall back to localStorage (Editor-side draft preview only). */
function getImages(num) {
  const it = itemsByNum[num];
  if (it && Array.isArray(it.media_files) && it.media_files.length > 0) {
    return it.media_files.slice();
  }
  let arr = getLocal(num, 'images', null);
  if (!Array.isArray(arr)) {
    const legacy = getLocal(num, 'img', '');
    arr = legacy ? [legacy] : [];
  }
  return arr;
}

function saveImages(num, arr) {
  setLocal(num, 'images', arr);
  try { localStorage.removeItem(lsKey(num, 'img')); } catch (e) {}
}

const MAX_MEDIA_SLOTS = 10;

function renderMediaSlots(num, images, ratioCls, isView, slides) {
  const parts = [];
  // The visual ITSELF carries the text (designed into the image). We do NOT display
  // the slide text as a separate block — it would be redundant with the image.
  // slides[] data still lives in data.json for future use (print view, accessibility, search).
  images.forEach((src, idx) => {
    parts.push(`
      <div class="media-card" data-idx="${idx}" data-num="${num}">
        <div class="media-slot ${ratioCls} has-image">
          <img class="media-img" src="${src}" alt="ויזואל ${idx + 1}" loading="lazy"
               onclick="openLightbox(${num}, ${idx})" />
          <div class="media-slot-num">${idx + 1}</div>
        </div>
        ${!isView ? `
          <div class="media-actions">
            <button class="media-act media-act-replace" title="החלף תמונה זו" onclick="event.stopPropagation(); triggerImageReplace(${num}, ${idx})">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
              <span>החלף</span>
            </button>
            <input type="file" class="media-replace-input" accept="image/*"
                   onchange="handleImageReplace(${num}, ${idx}, this.files[0])" />
            <button class="media-act media-act-trash" title="מחק תמונה זו" onclick="event.stopPropagation(); removeImageAt(${num}, ${idx})">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              <span>מחק</span>
            </button>
          </div>
        ` : ''}
      </div>
    `);
  });
  // Add-slot tile (always last when count < MAX, hidden in view mode)
  if (!isView && images.length < MAX_MEDIA_SLOTS) {
    parts.push(`
      <div class="media-card media-card-add" data-num="${num}">
        <div class="media-slot ${ratioCls} media-slot-add" onclick="triggerImageAdd(${num})">
          <input type="file" class="media-file-input" accept="image/*" onchange="handleImageAdd(${num}, this.files[0])" />
          <svg class="media-add-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          <div class="media-add-text">${images.length === 0 ? 'גרור תמונה או לחץ לבחירה' : 'הוסף תמונה'}</div>
          <div class="media-add-sub">PNG · JPG · WebP · עד ${MAX_MEDIA_SLOTS}</div>
        </div>
      </div>
    `);
  } else if (isView && images.length === 0) {
    parts.push(`<div class="media-card"><div class="media-slot ${ratioCls} media-slot-empty"><div class="media-empty-text">— אין עדיין תמונה —</div></div></div>`);
  }
  return parts.join('');
}

/* Render the slide's VISUAL COPY block — the text that appears ON the visual.
   This is DIFFERENT from copy_final (the caption / קופי נלווה) — that one stays in its
   own textarea. Here we show what's written INSIDE the image: ראשית/משנית/בקטן (posts)
   or the single line of text per carousel slide. */
function renderSlideCopy(slide) {
  if (!slide) return '';
  const lines = [];
  if (slide.label)     lines.push(`<div class="slide-copy-label">${escapeHtml(slide.label)}</div>`);
  if (slide.primary)   lines.push(`<div class="slide-copy-primary">${escapeHtml(slide.primary).replace(/\\n/g, '<br>')}</div>`);
  if (slide.secondary) lines.push(`<div class="slide-copy-secondary">${escapeHtml(slide.secondary).replace(/\\n/g, '<br>')}</div>`);
  if (slide.small)     lines.push(`<div class="slide-copy-small">${escapeHtml(slide.small).replace(/\\n/g, '<br>')}</div>`);
  if (slide.copy)      lines.push(`<div class="slide-copy-line">${escapeHtml(slide.copy).replace(/\\n/g, '<br>')}</div>`);
  if (lines.length === 0) return '';
  return `<div class="slide-copy" dir="rtl"><div class="slide-copy-title">📝 טקסט על הוויזואל</div>${lines.join('')}</div>`;
}

function triggerImageReplace(num, idx) {
  const card = document.querySelector('.media-card[data-num="' + num + '"][data-idx="' + idx + '"]');
  if (!card) return;
  const input = card.querySelector('.media-replace-input');
  if (input) input.click();
}

function handleImageReplace(num, idx, file) {
  if (!file || !file.type.startsWith('image/')) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    const arr = getImages(num);
    arr[idx] = e.target.result;
    saveImages(num, arr);
    refreshMediaGrid(num);
  };
  reader.readAsDataURL(file);
}

function triggerImageAdd(num) {
  const slot = document.querySelector('.media-slot-add[data-num="' + num + '"]');
  if (!slot) return;
  const input = slot.querySelector('.media-file-input');
  if (input) input.click();
}

function handleImageAdd(num, file) {
  if (!file || !file.type.startsWith('image/')) return;
  const arr = getImages(num);
  if (arr.length >= MAX_MEDIA_SLOTS) {
    alert(`הגעת למקסימום ${MAX_MEDIA_SLOTS} תמונות לפריט`);
    return;
  }
  const reader = new FileReader();
  reader.onload = (e) => {
    arr.push(e.target.result);
    saveImages(num, arr);
    refreshMediaGrid(num);
  };
  reader.readAsDataURL(file);
}

function removeImageAt(num, idx) {
  const arr = getImages(num);
  arr.splice(idx, 1);
  saveImages(num, arr);
  refreshMediaGrid(num);
}

function refreshMediaGrid(num) {
  const zone = document.querySelector('.media-zone[data-num="' + num + '"]');
  if (!zone) return;
  const grid = zone.querySelector('.media-grid');
  const ratioCls = zone.classList.contains('ratio-9-16') ? 'ratio-9-16' : 'ratio-1-1';
  const isView = isViewMode();
  const it = itemsByNum[num];
  grid.innerHTML = renderMediaSlots(num, getImages(num), ratioCls, isView, it ? it.slides : []);
  // Re-wire drag/drop on the new add-slot
  setupMediaDrop(num);
}

function setupMediaDrop(num) {
  const addSlot = document.querySelector('.media-slot-add[data-num="' + num + '"]');
  if (!addSlot) return;
  addSlot.addEventListener('dragover', (e) => { e.preventDefault(); addSlot.classList.add('drag-over'); });
  addSlot.addEventListener('dragleave', () => addSlot.classList.remove('drag-over'));
  addSlot.addEventListener('drop', (e) => {
    e.preventDefault();
    addSlot.classList.remove('drag-over');
    const f = e.dataTransfer.files[0];
    if (f && f.type.startsWith('image/')) handleImageAdd(num, f);
  });
}

/* ---------- Lightbox (click image to enlarge) ---------- */
function openLightbox(num, idx) {
  const arr = getImages(num);
  if (!arr[idx]) return;
  let lb = document.getElementById('lightbox');
  if (!lb) {
    lb = document.createElement('div');
    lb.id = 'lightbox';
    lb.className = 'lightbox';
    lb.innerHTML = `
      <button class="lightbox-close" onclick="closeLightbox()" aria-label="סגור">×</button>
      <button class="lightbox-prev" onclick="lightboxNav(-1)" aria-label="הקודם">‹</button>
      <img class="lightbox-img" id="lightboxImg" alt="ויזואל" />
      <button class="lightbox-next" onclick="lightboxNav(1)" aria-label="הבא">›</button>
      <div class="lightbox-counter" id="lightboxCounter"></div>
    `;
    lb.addEventListener('click', (e) => { if (e.target === lb) closeLightbox(); });
    document.body.appendChild(lb);
  }
  lb.dataset.num = num;
  lb.dataset.idx = idx;
  document.getElementById('lightboxImg').src = arr[idx];
  document.getElementById('lightboxCounter').textContent = `${idx + 1} / ${arr.length}`;
  lb.classList.add('open');
}
function closeLightbox() {
  const lb = document.getElementById('lightbox');
  if (lb) lb.classList.remove('open');
}
function lightboxNav(delta) {
  const lb = document.getElementById('lightbox');
  if (!lb) return;
  const num = parseInt(lb.dataset.num);
  const arr = getImages(num);
  let idx = parseInt(lb.dataset.idx) + delta;
  if (idx < 0) idx = arr.length - 1;
  if (idx >= arr.length) idx = 0;
  lb.dataset.idx = idx;
  document.getElementById('lightboxImg').src = arr[idx];
  document.getElementById('lightboxCounter').textContent = `${idx + 1} / ${arr.length}`;
}
document.addEventListener('keydown', (e) => {
  const lb = document.getElementById('lightbox');
  if (!lb || !lb.classList.contains('open')) return;
  if (e.key === 'Escape') closeLightbox();
  if (e.key === 'ArrowLeft') lightboxNav(-1);
  if (e.key === 'ArrowRight') lightboxNav(1);
});

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
updateDraftBar();
'''


def render_html(data: dict, logo_b64: str, mode: str = 'zeliger',
                view: bool = False, viewer_url: str = '', last_updated: str = '') -> str:
    """Render a single HTML file.

    view=False → Editor: full edit UI, draft bar, share/PDF/restore buttons
    view=True  → Viewer: read-only, no edit chrome at all (file is frozen, client-safe)
    """
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

    # PERIOD LABEL — ALWAYS shows ONE month at a time (the currently-viewed one).
    # We pre-compute a meta map { "YYYY-MM": {greg, heb} } and let JS update the label
    # whenever the month dropdown changes. Default = first chronological month.
    from israeli_holidays import hebrew_month_for_gregorian, hebrew_year_for_gregorian
    months_meta = {}
    for (y, m) in months:
        key = f'{y}-{m:02d}'
        months_meta[key] = {
            'greg': f'{HEB_GREG_MONTHS[m]} {y}',
            'heb':  f'{hebrew_month_for_gregorian(y, m)} {hebrew_year_for_gregorian(y, m)}',
        }
    months_meta_json = json.dumps(months_meta, ensure_ascii=False)
    # Initial label = first month
    y0, m0 = months[0]
    init_greg = f'{HEB_GREG_MONTHS[m0]} {y0}'
    init_heb = f'{hebrew_month_for_gregorian(y0, m0)} {hebrew_year_for_gregorian(y0, m0)}'
    canonical_period_html = (
        f'<span class="period-greg" id="periodGreg">{init_greg}</span>'
        f'<span class="period-dot">·</span>'
        f'<span class="period-heb" id="periodHeb">{init_heb}</span>'
    )

    # Client key for localStorage scoping (slug-ish)
    client_key = ''.join(c if c.isalnum() else '_' for c in client) or 'client'

    js_filled = (
        JS.replace('__ITEMS_JSON__', items_json)
          .replace('__CLIENT_KEY__', client_key)
          .replace('__MONTHS_META_JSON__', months_meta_json)
          .replace('__VIEW_MODE_BAKED__', 'true' if view else 'false')
          .replace('__VIEWER_URL__', viewer_url)
          .replace('__LAST_UPDATED__', last_updated)
    )

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
        # English brand name + × separator (brand-kit signature). Name clickable → WhatsApp.
        # Text is verbatim from CV v2 (uria-berman-cv/public/v2/index.html) — the canonical "דברו איתי" CTA.
        wa_text = 'היי אוריה, קורות החיים שלך - וואו! בא לי שנעשה דברים מעניינים יחד.'
        wa_url = f'https://wa.me/972548825232?text={urllib.parse.quote(wa_text)}'
        footer_text = (
            '<span class="footer-built">Built by</span>'
            '<span class="footer-x">×</span>'
            f'<a class="footer-brand footer-link-wa" href="{wa_url}" target="_blank" rel="noopener" title="לדבר איתי בוואטסאפ">Uria Berman'
            '<span class="footer-period">.</span>'
            '</a>'
        )
    else:
        logo_tag = (
            f'<a class="brand-link" href="https://zst.co.il/" target="_blank" rel="noopener" title="זליגר שומרון">'
            f'<img class="logo" src="data:image/png;base64,{logo_b64}" alt="Zeliger Shomron" />'
            f'</a>'
        )
        footer_text = (
            'Built by <span class="footer-brand">Social · '
            '<a class="footer-link" href="https://zst.co.il/" target="_blank" rel="noopener">Zeliger Shomron</a>'
            '</span>'
        )

    css_with_theme = CSS.replace('__THEME_ROOT__', render_theme_root(mode))
    if mode == 'uria':
        css_with_theme += URIA_OVERRIDES

    # Font links: load both Inter (Zeliger) and Plus Jakarta Sans (Uria)
    font_links = ('<link href="https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Heebo:wght@400;500;700&display=swap" rel="stylesheet">')

    body_class = f'theme-{mode}'
    if view:
        body_class += ' view-mode'

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
      <div class="period-mini">{canonical_period_html}</div>
      <h1><span class="h1-label">גאנט חודשי</span><span class="h1-sep">{('<span class="x-box-mini">×</span>' if mode == 'uria' else '·')}</span><span class="h1-client">{html.escape(client)}</span></h1>
      <span class="header-hint">{('לחץ על קוביה לצפייה בפרטים' if view else 'גרור קוביה כדי להזיז · לחץ לעריכה')}</span>
    </div>
  </header>

  {('' if view else '''
  <div class="draft-bar" id="draftBar" hidden>
    <span class="draft-bar-text">⚠ יש לך שינויים בטיוטה — הלקוח עדיין לא רואה אותם</span>
    <div class="draft-bar-actions">
      <button class="draft-bar-publish" onclick="requestPublish()">📤 פרסם שינויים</button>
      <button class="draft-bar-discard" onclick="discardDraft()">בטל הכל</button>
    </div>
  </div>
  ''')}

  <div class="controls">
    {legend_html}
    <div class="control-cluster">
      {('' if view else '''
      <button class="share-btn" id="shareBtn" onclick="shareView(this)" title="העתק קישור צפייה ללקוח">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
        <span>שיתוף</span>
      </button>
      <button class="pdf-btn" id="pdfBtn" onclick="downloadPDF()" title="הורד גאנט כ-PDF">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        <span>הורד כ-PDF</span>
      </button>
      <button class="restore-btn" id="restoreBtn" onclick="restoreOriginal()" title="החזר את כל התכנים למיקומם המקורי">
        <span>↺ החזר למקור</span>
      </button>
      ''')}
      {tabs_html}
    </div>
  </div>

  <div class="months-container">
    {''.join(months_html_parts)}
  </div>

  <div class="footer-meta">
    {('<span class="last-updated">עודכן לאחרונה: <span id="lastUpdatedTime">' + html.escape(last_updated) + '</span></span>') if last_updated else ''}
    <span class="view-mode-badge">{('מצב צפייה · ללא עריכה' if view else 'מצב עריכה')}</span>
  </div>
  <div class="footer" dir="ltr">{footer_text}</div>
</div>

{('' if view else '''
<!-- Floating preview-mode toggle — only on Editor URL. Lets Uria see exactly what the client sees. -->
<button class="preview-toggle" id="previewToggle" onclick="togglePreviewMode()" title="עבור בין מצב עריכה למצב צפייה (כמו שהלקוח רואה)">
  <svg class="preview-toggle-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>
  <span class="preview-toggle-label">צפה כלקוח</span>
</button>
<div class="preview-banner" id="previewBanner" hidden>
  <span>👁 אתה רואה את הגאנט כפי שהלקוח רואה אותו</span>
</div>
''')}

<div class="modal-bg" id="modal">
  <div class="modal" id="modal-inner"></div>
</div>

<script>{js_filled}</script>
</body>
</html>
'''


def _now_he_he() -> str:
    """Return current Israel time as 'DD.M.YY, HH:MM' for the 'עודכן לאחרונה' footer."""
    from datetime import datetime, timezone, timedelta
    tz_il = timezone(timedelta(hours=3))  # Israel summer time approx (good enough for footer)
    now = datetime.now(tz_il)
    return now.strftime('%d.%m.%y, %H:%M')


def _sync_media(pilot_dir: Path, out_dir: Path):
    """Copy pilots/{slug}/media/* → docs/{slug}/media/* so client URLs serve images.
    File naming convention: {num}-{idx}.{ext}  (e.g. 5-0.jpg, 5-1.png, 12-0.webp)
    """
    src = pilot_dir / 'media'
    if not src.exists():
        return []
    dst = out_dir / 'media'
    dst.mkdir(parents=True, exist_ok=True)
    import shutil
    copied = []
    for f in src.iterdir():
        if f.is_file() and f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp', '.gif'}:
            shutil.copy2(f, dst / f.name)
            copied.append(f.name)
    return copied


def _media_index_for_data(pilot_dir: Path, items: list) -> dict:
    """Scan pilots/{slug}/media/ and group files by item num.
    Returns {num: ['media/1-0.jpg', 'media/1-1.png', ...]} for each item.
    """
    media_dir = pilot_dir / 'media'
    if not media_dir.exists():
        return {}
    idx = {}
    for f in sorted(media_dir.iterdir()):
        if not f.is_file():
            continue
        if f.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp', '.gif'}:
            continue
        # Expected: {num}-{idx}.{ext}
        stem = f.stem
        if '-' not in stem:
            continue
        try:
            num_str, idx_str = stem.split('-', 1)
            num = int(num_str)
            sort_key = int(idx_str)
        except ValueError:
            continue
        idx.setdefault(num, []).append((sort_key, f'media/{f.name}'))
    # Sort each item's images by their slot idx
    return {num: [path for (_, path) in sorted(paths)] for num, paths in idx.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True, help='Path to pilots/{slug}/data.json')
    ap.add_argument('--logo', required=True)
    ap.add_argument('--out', required=True, help='Path to docs/{slug}/index.html (Editor). The Viewer is auto-built at docs/{slug}/view/index.html')
    ap.add_argument('--mode', choices=['zeliger', 'uria'], default='zeliger',
                    help='Brand mode: zeliger (default, dark) or uria (dark aubergine, brand kit)')
    ap.add_argument('--base-url', default='https://uriaberman.github.io/zst-monthly-gantt',
                    help='Base URL prefix used to compute the Viewer URL baked into the Editor')
    args = ap.parse_args()

    data_path = Path(args.data)
    data = json.loads(data_path.read_text(encoding='utf-8'))
    logo_b64 = base64.b64encode(Path(args.logo).read_bytes()).decode('ascii')

    # Compute Israeli holidays for the period of the data
    dates = sorted([it['date_iso'] for it in data['items'] if it.get('date_iso')])
    if dates:
        from israeli_holidays import get_israeli_holidays, hebrew_month_for_gregorian, hebrew_year_for_gregorian
        from datetime import date, timedelta
        first = date.fromisoformat(dates[0])
        last = date.fromisoformat(dates[-1])
        start_ext = (first - timedelta(days=7)).isoformat()
        end_ext = (last + timedelta(days=7)).isoformat()
        holidays = get_israeli_holidays(start_ext, end_ext)
        HOLIDAYS_2026.update(holidays)
        heb_month = hebrew_month_for_gregorian(first.year, first.month)
        heb_year = hebrew_year_for_gregorian(first.year, first.month)
        data['_heb_month'] = heb_month
        data['_heb_year'] = heb_year

    # File-based media: scan pilots/{slug}/media/ and inject relative paths into each item
    pilot_dir = data_path.parent
    media_idx = _media_index_for_data(pilot_dir, data['items'])
    for it in data['items']:
        if it['num'] in media_idx:
            it['media_files'] = media_idx[it['num']]

    out_editor = Path(args.out)
    out_dir = out_editor.parent
    out_viewer = out_dir / 'view' / 'index.html'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_viewer.parent.mkdir(parents=True, exist_ok=True)

    # Compute slug + Viewer URL for embedding into the Editor's share button
    slug = out_dir.name
    viewer_url = f'{args.base_url.rstrip("/")}/{slug}/view/'

    # Last-updated timestamp (Israel time)
    last_updated = _now_he_he()
    data['published_at'] = last_updated

    # Copy media files to BOTH docs/{slug}/media/ and docs/{slug}/view/media/
    copied_main = _sync_media(pilot_dir, out_dir)
    copied_view = _sync_media(pilot_dir, out_viewer.parent)

    # Build Editor (full edit UI)
    editor_html = render_html(data, logo_b64, mode=args.mode, view=False,
                              viewer_url=viewer_url, last_updated=last_updated)
    out_editor.write_text(editor_html, encoding='utf-8')
    print(f'WROTE EDITOR  {out_editor} ({len(editor_html):,} chars)')

    # Build Viewer (read-only, frozen at this moment)
    viewer_html = render_html(data, logo_b64, mode=args.mode, view=True,
                              viewer_url=viewer_url, last_updated=last_updated)
    out_viewer.write_text(viewer_html, encoding='utf-8')
    print(f'WROTE VIEWER  {out_viewer} ({len(viewer_html):,} chars)')

    print(f'  Mode: {args.mode}')
    print(f'  Slug: {slug}')
    print(f'  Last updated (IL): {last_updated}')
    if copied_main:
        print(f'  Media files copied: {len(copied_main)} → {", ".join(copied_main[:5])}{"..." if len(copied_main) > 5 else ""}')
    else:
        print(f'  Media files: none (drop {pilot_dir}/media/{{num}}-{{idx}}.jpg)')
    if HOLIDAYS_2026:
        print(f'  Israeli holidays in period: {len(HOLIDAYS_2026)}')

    # ============================================================
    # CRITICAL VERIFICATION (per iron rule: media MUST render in modal)
    # ============================================================
    # We had a bug (24.5.2026) where pilots had media files on disk but the modal
    # silently rendered without them because two code paths read media differently.
    # This block detects that class of regression at BUILD time, before push.
    if copied_main:
        items_with_media = [it for it in data['items'] if it.get('media_files')]
        # 1. Every item that has files on disk must have media_files baked into HTML
        for it in data['items']:
            num = it['num']
            disk_files = [p for p in (pilot_dir / 'media').iterdir() if p.is_file() and p.stem.startswith(f'{num}-')]
            baked_files = it.get('media_files', [])
            if disk_files and not baked_files:
                raise SystemExit(f'  VERIFY FAILED: item #{num} has {len(disk_files)} files on disk but 0 in data → would render empty modal')
        # 2. Every baked media_files entry must be discoverable in BOTH output HTMLs as a path
        for it in items_with_media:
            for path in it['media_files']:
                if path not in editor_html or path not in viewer_html:
                    raise SystemExit(f'  VERIFY FAILED: media path "{path}" missing from {("Editor" if path not in editor_html else "Viewer")} HTML')
        # 3. Every output media folder must have the actual file
        for it in items_with_media:
            for path in it['media_files']:
                full = out_dir / path
                if not full.exists():
                    raise SystemExit(f'  VERIFY FAILED: {full} not on disk after build')
                full_view = out_viewer.parent / path
                if not full_view.exists():
                    raise SystemExit(f'  VERIFY FAILED: {full_view} not on disk after build (viewer)')
        print(f'  ✅ Media verification PASS — {len(items_with_media)} items, {sum(len(it["media_files"]) for it in items_with_media)} total slides')

    # ============================================================
    # COPY COMPLETENESS WARNING (iron rule 16)
    # ============================================================
    # A gantt has THREE kinds of text — all three must be captured from the source:
    #   1. copy_final  — the caption/social-post text (קופי נלווה)
    #   2. slides[].primary/secondary/small/copy — visual text on each slide (טקסט על הוויזואל)
    #   3. short_explanation — the rationale shown in the modal
    # If an item has media but no slides[] copy, the modal would show only the image and no text
    # — which is the 24.5.26 regression. Warn loudly (not block — copy can be a TBD).
    missing_visual_copy = []
    missing_caption = []
    for it in data['items']:
        files = it.get('media_files', []) or []
        slides = it.get('slides', []) or []
        if files and not slides:
            missing_visual_copy.append(it['num'])
        elif files and slides:
            # Check each slide has at least one of: primary, secondary, small, copy
            for idx, slide in enumerate(slides):
                has_text = any(slide.get(k) for k in ('primary', 'secondary', 'small', 'copy'))
                if not has_text and idx < len(files):
                    missing_visual_copy.append(f"{it['num']}-{idx}")
                    break
        if not it.get('copy_final'):
            missing_caption.append(it['num'])
    if missing_visual_copy:
        print(f'  ⚠ WARN: items missing טקסט-על-הוויזואל (slides[]): {missing_visual_copy}')
    if missing_caption:
        print(f'  ⚠ WARN: items missing קופי נלווה (copy_final): {missing_caption}')


if __name__ == '__main__':
    main()
